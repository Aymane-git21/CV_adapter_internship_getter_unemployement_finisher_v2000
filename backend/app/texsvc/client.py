"""HTTP client for services/latexc. Returns the Typst CompileResult shape so
routers dispatch once and stay engine-agnostic."""
import base64
import logging

import httpx
from services.latexc.contract import CompileFile, LatexCompileIn, LatexCompileOut

from ..config import get_settings
from ..typstsvc.renderer import CompileResult

log = logging.getLogger("cvglowup.latexc")

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = httpx.AsyncClient(
            base_url=s.latexc_url,
            headers={"Authorization": f"Bearer {s.latexc_token}"},
            timeout=50.0,
        )
    return _client


async def compile_tex(doc_id: str, tex_source: str) -> tuple[CompileResult, str]:
    body = LatexCompileIn(
        doc_id=doc_id,
        files=[CompileFile(
            path="main.tex",
            content_b64=base64.b64encode(tex_source.encode("utf-8")).decode(),
        )],
    )
    try:
        resp = await _http().post("/v1/compile", json=body.model_dump())
        resp.raise_for_status()
        out = LatexCompileOut.model_validate(resp.json())
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("latexc unreachable: %s", exc)
        return (
            CompileResult(ok=False, diagnostics=f"LaTeX service unavailable: {exc}"),
            tex_source,
        )
    log.info(
        "latex_compile doc=%s cache=%s ok=%s pages=%s total_ms=%s",
        doc_id, out.cache, out.ok, out.pages, out.timings_ms.get("total"),
    )
    if not out.ok:
        diag = (out.error_line or "LaTeX compile failed") + "\n\n" + out.log_tail[-4000:]
        return CompileResult(ok=False, diagnostics=diag), tex_source
    pdf = base64.b64decode(out.pdf_b64) if out.pdf_b64 else None
    return CompileResult(ok=True, pages=out.pages, pdf=pdf, svgs=out.svgs), tex_source


async def service_status() -> bool:
    """Is the warm service answering right now? Short timeout on purpose."""
    try:
        resp = await _http().get("/v1/status", timeout=3.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


async def clear_project(doc_id: str) -> bool:
    try:
        resp = await _http().delete(f"/v1/project/{doc_id}")
        return resp.status_code in (204, 404)
    except httpx.HTTPError:
        return False
