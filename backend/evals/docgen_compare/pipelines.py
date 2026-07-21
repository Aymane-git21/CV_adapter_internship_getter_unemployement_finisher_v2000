"""Toolchain adapters: compile one source file in a workdir, normalized result.

Tool discovery: env override first (CVG_QUARTO_BIN / CVG_TECTONIC_BIN), then
the repo-local portable installs under .tools/ (see setup_tools.ps1), then
PATH. Typst reuses the app's own discovery (backend.app.config).
"""
import asyncio
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from backend.app.config import get_settings

from . import prompts_bench

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / ".tools"
REFERENCES = Path(__file__).resolve().parent / "references"

_DIAG_LIMIT = 4000


def _find_tool(env_var: str, tools_subdir: str, exe_name: str) -> str | None:
    override = os.environ.get(env_var)
    if override and Path(override).exists():
        return override
    local = TOOLS_DIR / tools_subdir
    if local.is_dir():
        hit = next(local.rglob(exe_name), None)
        if hit:
            return str(hit)
    return shutil.which(exe_name.removesuffix(".exe"))


def typst_bin() -> str:
    return get_settings().typst_command


def quarto_bin() -> str | None:
    return _find_tool("CVG_QUARTO_BIN", "quarto", "quarto.exe")


def tectonic_bin() -> str | None:
    return _find_tool("CVG_TECTONIC_BIN", "tectonic", "tectonic.exe")


@dataclass
class CompileOutcome:
    ok: bool
    ms: int
    pdf: Path | None
    diagnostics: str


def _abs_workdir(workdir: Path) -> Path:
    """Compilers get absolute paths for --root/--outdir; callers may pass relative."""
    return workdir.resolve()


async def _run(cmd: list[str], cwd: Path, timeout_s: float) -> tuple[int, str, int]:
    """Return (exit_code, combined_output_tail, elapsed_ms)."""
    t0 = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        return 1, f"compilation timed out after {timeout_s:.0f}s", int((time.perf_counter() - t0) * 1000)
    ms = int((time.perf_counter() - t0) * 1000)
    text = (
        stderr.decode("utf-8", errors="replace") + "\n" + stdout.decode("utf-8", errors="replace")
    ).strip()
    # Errors sit at the tail for all three toolchains; keep the tail.
    if len(text) > _DIAG_LIMIT:
        text = "…" + text[-_DIAG_LIMIT:]
    return proc.returncode or 0, text, ms


class Pipeline:
    name: str
    ext: str
    label: str
    notes: str
    ref: Path

    def available(self) -> str | None:
        """Return the binary path if usable, else None."""
        raise NotImplementedError

    async def compile(self, workdir: Path, filename: str) -> CompileOutcome:
        raise NotImplementedError


class TypstPipeline(Pipeline):
    name = "typst"
    ext = ".typ"
    label = "Typst (v0.14)"
    notes = prompts_bench.TYPST_NOTES
    ref = REFERENCES / "ref.typ"

    def available(self) -> str | None:
        binary = typst_bin()
        return binary if shutil.which(binary) or Path(binary).exists() else None

    async def compile(self, workdir: Path, filename: str) -> CompileOutcome:
        workdir = _abs_workdir(workdir)
        out = workdir / "out.pdf"
        code, diag, ms = await _run(
            [typst_bin(), "compile", filename, "out.pdf", "--root", str(workdir)],
            cwd=workdir,
            timeout_s=60,
        )
        ok = code == 0 and out.exists()
        return CompileOutcome(ok=ok, ms=ms, pdf=out if ok else None, diagnostics="" if ok else diag)


class QuartoPipeline(Pipeline):
    name = "quarto"
    ext = ".qmd"
    label = "Quarto markdown (rendered to Typst)"
    notes = prompts_bench.QMD_NOTES
    ref = REFERENCES / "ref.qmd"

    def available(self) -> str | None:
        return quarto_bin()

    async def compile(self, workdir: Path, filename: str) -> CompileOutcome:
        workdir = _abs_workdir(workdir)
        binary = quarto_bin()
        if binary is None:
            return CompileOutcome(ok=False, ms=0, pdf=None, diagnostics="quarto not installed")
        code, diag, ms = await _run(
            [binary, "render", filename, "--to", "typst"],
            cwd=workdir,
            timeout_s=240,
        )
        pdf = workdir / (Path(filename).stem + ".pdf")
        ok = code == 0 and pdf.exists()
        return CompileOutcome(ok=ok, ms=ms, pdf=pdf if ok else None, diagnostics="" if ok else diag)


class TectonicPipeline(Pipeline):
    name = "tectonic"
    ext = ".tex"
    label = "LaTeX (compiled by Tectonic/XeTeX)"
    notes = prompts_bench.LATEX_NOTES
    ref = REFERENCES / "ref.tex"

    def available(self) -> str | None:
        return tectonic_bin()

    async def compile(self, workdir: Path, filename: str) -> CompileOutcome:
        workdir = _abs_workdir(workdir)
        binary = tectonic_bin()
        if binary is None:
            return CompileOutcome(ok=False, ms=0, pdf=None, diagnostics="tectonic not installed")
        code, diag, ms = await _run(
            [binary, "-X", "compile", "--outdir", str(workdir), filename],
            cwd=workdir,
            timeout_s=300,
        )
        pdf = workdir / (Path(filename).stem + ".pdf")
        ok = code == 0 and pdf.exists()
        return CompileOutcome(ok=ok, ms=ms, pdf=pdf if ok else None, diagnostics="" if ok else diag)


PIPELINES: dict[str, Pipeline] = {
    p.name: p for p in (TypstPipeline(), QuartoPipeline(), TectonicPipeline())
}


async def tool_version(binary: str | None, timeout_s: float = 30) -> str:
    if not binary:
        return "not installed"
    try:
        code, out, _ = await _run([binary, "--version"], cwd=REPO_ROOT, timeout_s=timeout_s)
        first = out.strip().splitlines()[0] if out.strip() else ""
        return first if code == 0 else f"error: {first}"
    except (OSError, FileNotFoundError) as exc:
        return f"error: {exc}"


def dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 1)


def toolchain_footprints() -> dict[str, float]:
    """Installed size per toolchain in MB (what a Docker image would carry)."""
    typst_path = Path(typst_bin()) if Path(typst_bin()).exists() else None
    tectonic_cache = Path(os.environ.get("LOCALAPPDATA", "")) / "TectonicProject"
    return {
        "typst": round((typst_path.stat().st_size / (1024 * 1024)), 1) if typst_path else 0.0,
        "quarto": dir_size_mb(TOOLS_DIR / "quarto"),
        "tectonic": round(dir_size_mb(TOOLS_DIR / "tectonic") + dir_size_mb(tectonic_cache), 1),
    }
