"""latexmk/pdftocairo subprocess layer. Hardening lives here: no shell
escape, paranoid openin/openout, per-project TEXMF state, hard timeout with
process-group kill, capped log tails."""
import asyncio
import base64
import json
import os
import re
import signal
from pathlib import Path

from .contract import MAX_TOTAL_BYTES, CompileFile

LOG_TAIL_BYTES = 20_000


class CompileError(Exception):
    pass


def sync_files(pdir: Path, files: list[CompileFile]) -> None:
    """Write the request's files; delete user files from previous requests
    that were not re-sent (aux/fdb/latexmk state stays, that IS the cache)."""
    pdir.mkdir(parents=True, exist_ok=True)
    total = 0
    names: list[str] = []
    for f in files:
        if "/" in f.path or "\\" in f.path or ".." in f.path:
            raise CompileError(f"illegal path: {f.path}")
        try:
            raw = base64.b64decode(f.content_b64, validate=True)
        except Exception as exc:
            raise CompileError(f"bad base64 for {f.path}") from exc
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise CompileError("files too large")
        (pdir / f.path).write_bytes(raw)
        names.append(f.path)

    manifest = pdir / "manifest.json"
    if manifest.exists():
        try:
            previous = json.loads(manifest.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            previous = []
        for stale in set(previous) - set(names):
            (pdir / stale).unlink(missing_ok=True)
    manifest.write_text(json.dumps(sorted(names)), encoding="utf-8")


async def _run(cmd: list[str], cwd: Path, env: dict, timeout_s: int) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        await proc.wait()
        return 124, f"timed out after {timeout_s}s"
    return proc.returncode or 0, out.decode("utf-8", errors="replace")


def _tex_env(pdir: Path) -> dict:
    env = dict(os.environ)
    env.update(
        {
            "HOME": str(pdir),
            "TEXMFVAR": str(pdir / ".texmf-var"),
            "TEXMFCONFIG": str(pdir / ".texmf-cfg"),
            "TEXMFHOME": str(pdir / ".texmf-home"),
            "openout_any": "p",
            "openin_any": "p",
        }
    )
    return env


def log_tail(pdir: Path, main: str, fallback: str) -> str:
    log = pdir / (Path(main).stem + ".log")
    if log.exists():
        data = log.read_bytes()[-LOG_TAIL_BYTES:]
        return data.decode("utf-8", errors="replace")
    return fallback[-LOG_TAIL_BYTES:]


def first_error_line(log: str) -> str | None:
    m = re.search(r"^(?:! (.+)|.+?:\d+: (.+))$", log, re.MULTILINE)
    if not m:
        if "timed out" in log:
            return log.splitlines()[0][:200] if log else None
        return None
    return (m.group(1) or m.group(2)).strip()[:300]


async def compile_latex(pdir: Path, main: str, timeout_s: int) -> tuple[bool, str]:
    """Run latexmk -xelatex in the project dir. Aux files persist on purpose."""
    cmd = [
        "latexmk",
        "-xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-no-shell-escape",
        # -g forces a run even when latexmk considers outputs current: we only
        # get here when the content key CHANGED (the hit cache short-circuits
        # true no-ops), and without it a deleted include serves a stale PDF.
        "-g",
        main,
    ]
    code, out = await _run(cmd, pdir, _tex_env(pdir), timeout_s)
    return code == 0, out


async def pdf_pages(pdir: Path, pdf_name: str) -> int:
    code, out = await _run(["pdfinfo", pdf_name], pdir, _tex_env(pdir), 20)
    if code != 0:
        raise CompileError(f"pdfinfo failed: {out[:200]}")
    m = re.search(r"^Pages:\s+(\d+)", out, re.MULTILINE)
    if not m:
        raise CompileError("pdfinfo gave no page count")
    return int(m.group(1))


async def pdf_to_svgs(pdir: Path, pdf_name: str, pages: int) -> list[str]:
    svgs: list[str] = []
    for n in range(1, pages + 1):
        out_name = f"page-{n}.svg"
        code, out = await _run(
            ["pdftocairo", "-svg", "-f", str(n), "-l", str(n), pdf_name, out_name],
            pdir, _tex_env(pdir), 30,
        )
        if code != 0:
            raise CompileError(f"pdftocairo failed on page {n}: {out[:200]}")
        svgs.append((pdir / out_name).read_text(encoding="utf-8"))
    return svgs
