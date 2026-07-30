"""latexc: warm sandboxed LaTeX compile service (CLSI-style).

One long-lived container; per-document compile dirs persist between requests
so recompiles reuse latexmk's aux state. Bearer-token auth on every route.
Never route anything at /healthz (Google's edge intercepts that path on
*.run.app); health is GET /v1/status."""
import asyncio
import base64
import hmac
import logging
import os
import time
from collections import defaultdict
from importlib import resources

from fastapi import Depends, FastAPI, HTTPException, Request

from . import cache, runner
from .contract import LatexCompileIn, LatexCompileOut, LatexStatus

log = logging.getLogger("latexc")
logging.basicConfig(level=logging.INFO, format="%(asctime)s latexc %(message)s")

_START = time.time()
_MAX_TEX_PROCS = int(os.environ.get("LATEXC_CONCURRENCY", "2"))
_tex_sem = asyncio.Semaphore(_MAX_TEX_PROCS)
_doc_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def _token() -> str:
    tok = os.environ.get("LATEXC_TOKEN", "")
    if not tok:
        raise RuntimeError("LATEXC_TOKEN is not set; refusing to serve")
    return tok


async def require_auth(request: Request) -> None:
    header = request.headers.get("authorization", "")
    supplied = header.removeprefix("Bearer ").strip()
    if not supplied or not hmac.compare_digest(supplied, _token()):
        raise HTTPException(status_code=401, detail="bad token")


@app.on_event("startup")
async def prewarm() -> None:
    _token()  # fail fast on missing token
    try:
        probe = resources.files("latexc").joinpath("probe.tex").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        probe = None
    if probe is None:
        log.warning("probe.tex missing; skipping prewarm")
        return
    t0 = time.time()
    body = LatexCompileIn(
        doc_id="_probe",
        files=[{"path": "main.tex", "content_b64": base64.b64encode(probe.encode()).decode()}],
        want_svgs=False,
    )
    try:
        out = await _compile(body)
        log.info("prewarm ok=%s in %.1fs", out.ok, time.time() - t0)
        if not out.ok:
            log.error("prewarm compile failed: %s", out.error_line or out.log_tail[-500:])
    except Exception:
        log.exception("prewarm crashed (service continues)")


async def _compile(inp: LatexCompileIn) -> LatexCompileOut:
    t_start = time.time()
    pdir = cache.project_dir(inp.doc_id)
    key = cache.content_key(inp)

    async with _doc_locks[inp.doc_id]:
        cached = cache.load_cached(pdir, key)
        if cached is not None:
            pdir.touch()  # bump LRU
            return LatexCompileOut(
                ok=True, cache="hit", pages=cached["pages"],
                pdf_b64=base64.b64encode(cached["pdf"]).decode(),
                svgs=cached["svgs"] if inp.want_svgs else [],
                timings_ms={"total": int((time.time() - t_start) * 1000)},
            )

        warmth = "warm" if pdir.exists() else "cold"
        t_sync = time.time()
        try:
            runner.sync_files(pdir, inp.files)
        except runner.CompileError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        t_tex = time.time()
        async with _tex_sem:
            ok, out = await runner.compile_latex(pdir, inp.main, inp.timeout_s)
        tail = runner.log_tail(pdir, inp.main, out)
        if not ok:
            return LatexCompileOut(
                ok=False, cache=warmth, log_tail=tail,
                error_line=runner.first_error_line(tail) or runner.first_error_line(out),
                timings_ms={
                    "sync": int((t_tex - t_sync) * 1000),
                    "compile": int((time.time() - t_tex) * 1000),
                    "total": int((time.time() - t_start) * 1000),
                },
            )

        t_convert = time.time()
        pdf_name = os.path.splitext(inp.main)[0] + ".pdf"
        try:
            pages = await runner.pdf_pages(pdir, pdf_name)
            svgs = await runner.pdf_to_svgs(pdir, pdf_name, pages) if inp.want_svgs else []
        except runner.CompileError as exc:
            return LatexCompileOut(ok=False, cache=warmth, log_tail=tail, error_line=str(exc))

        pdf_bytes = (pdir / pdf_name).read_bytes()
        cache.store(pdir, key, pages, pdf_bytes, svgs)
        cache.evict(keep=pdir)
        return LatexCompileOut(
            ok=True, cache=warmth, pages=pages,
            pdf_b64=base64.b64encode(pdf_bytes).decode(),
            svgs=svgs, log_tail=tail,
            timings_ms={
                "sync": int((t_tex - t_sync) * 1000),
                "compile": int((t_convert - t_tex) * 1000),
                "convert": int((time.time() - t_convert) * 1000),
                "total": int((time.time() - t_start) * 1000),
            },
        )


@app.post("/v1/compile", response_model=LatexCompileOut, dependencies=[Depends(require_auth)])
async def compile_endpoint(inp: LatexCompileIn) -> LatexCompileOut:
    out = await _compile(inp)
    log.info(
        "compile doc=%s cache=%s ok=%s pages=%s total_ms=%s",
        inp.doc_id, out.cache, out.ok, out.pages, out.timings_ms.get("total"),
    )
    return out


@app.delete("/v1/project/{doc_id}", status_code=204, dependencies=[Depends(require_auth)])
async def clear_project(doc_id: str) -> None:
    async with _doc_locks[doc_id]:
        cache.clear_project(doc_id)


@app.get("/v1/status", response_model=LatexStatus, dependencies=[Depends(require_auth)])
async def status() -> LatexStatus:
    projects, disk_mb = cache.stats()
    return LatexStatus(uptime_s=int(time.time() - _START), projects=projects, disk_mb=disk_mb)
