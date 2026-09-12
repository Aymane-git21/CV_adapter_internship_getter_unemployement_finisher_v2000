"""Typst rendering service.

Design notes:
- Documents are SELF-CONTAINED Typst sources: the data is embedded as a Typst
  dict literal, so what the user sees in the source editor is the whole truth
  and is directly editable (the Overleaf feel).
- Compiles run inside {templates_dir}/.compile/<uuid>/ with --root set to the
  templates dir. That jail means user-edited source can only read() template
  files and its own data/photo — never .env or anything else.
- Every document is ONE continuous page: the templates set `height: auto`, so
  the page ends where the content does. A4 pagination and its one-page fit
  loop (density tightening, font upscaling, overflow reporting) were removed
  on 2026-09-12, which makes rendering a document a single typst run.
"""
import asyncio
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..config import get_settings

_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

_semaphore: asyncio.Semaphore | None = None


def _sem() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().compile_concurrency)
    return _semaphore


# ---------------------------------------------------------------------------
# JSON -> Typst literal (for generated, human-editable source)
# ---------------------------------------------------------------------------


def _typst_str(s: str) -> str:
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
    return f'"{out}"'


def typst_literal(value, indent: int = 0) -> str:
    pad = "  " * indent
    inner = "  " * (indent + 1)
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _typst_str(value)
    if isinstance(value, list):
        if not value:
            return "()"
        if len(value) == 1:
            return f"({typst_literal(value[0], indent)},)"
        items = ",\n".join(inner + typst_literal(v, indent + 1) for v in value)
        return f"(\n{items},\n{pad})"
    if isinstance(value, dict):
        if not value:
            return "(:)"
        rows = []
        for k, v in value.items():
            key = k if _IDENT.match(str(k)) else _typst_str(str(k))
            rows.append(f"{inner}{key}: {typst_literal(v, indent + 1)}")
        return "(\n" + ",\n".join(rows) + f",\n{pad})"
    raise TypeError(f"Cannot render {type(value)} as Typst literal")


def template_file(kind: str, template_id: str) -> str:
    if kind == "letter":
        return "letter.typ"
    safe = template_id if re.match(r"^[a-z0-9_-]+$", template_id or "") else "onyx"
    return f"cv_{safe}.typ"


def render_source(kind: str, template_id: str, data: dict, settings: dict, has_photo: bool) -> str:
    """Produce the self-contained, editable Typst source for a document."""
    photo_line = (
        '#let photo = read("photo.jpg", encoding: none)' if has_photo else "#let photo = none"
    )
    return (
        f'#import "/typst/{template_file(kind, template_id)}": render\n'
        "\n"
        "// ── Document settings ──────────────────────────────────────────────\n"
        f"#let settings = {typst_literal(settings)}\n"
        "\n"
        "// ── Content — edit freely, the preview recompiles live ─────────────\n"
        f"#let data = {typst_literal(data)}\n"
        "\n"
        f"{photo_line}\n"
        "#render(data, settings, photo: photo)\n"
    )


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


@dataclass
class CompileResult:
    ok: bool
    pages: int = 0
    pdf: bytes | None = None
    svgs: list[str] = field(default_factory=list)
    diagnostics: str = ""


def _clean_diagnostics(stderr: str, jail: Path) -> str:
    txt = stderr.replace(str(jail), "").replace("\\", "/")
    # Trim absolute path noise; keep typst's own messages which are excellent.
    return txt.strip()[:4000]


async def _run_typst(args: list[str]) -> tuple[int, str, str]:
    settings = get_settings()
    proc = await asyncio.create_subprocess_exec(
        settings.typst_command,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except TimeoutError:
        proc.kill()
        return 1, "", "Compilation timed out after 30s"
    return proc.returncode or 0, stdout.decode("utf-8", errors="replace"), stderr.decode(
        "utf-8", errors="replace"
    )


async def compile_source(
    source: str,
    photo: bytes | None = None,
    fmt: str = "svg",
) -> CompileResult:
    """Compile a self-contained Typst source inside the jail. fmt: svg | pdf."""
    settings = get_settings()
    jail_root = settings.templates_dir
    workdir = jail_root / ".compile" / uuid.uuid4().hex
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        (workdir / "main.typ").write_text(source, encoding="utf-8")
        if photo is not None:
            (workdir / "photo.jpg").write_bytes(photo)

        common = [
            "compile",
            str(workdir / "main.typ"),
            "--root",
            str(jail_root),
            "--font-path",
            str(jail_root / "typst" / "fonts"),
        ]

        async with _sem():
            if fmt == "pdf":
                out = workdir / "out.pdf"
                code, _, stderr = await _run_typst([*common, str(out)])
                if code != 0:
                    return CompileResult(ok=False, diagnostics=_clean_diagnostics(stderr, workdir))
                return CompileResult(ok=True, pdf=out.read_bytes(), pages=1)
            out = workdir / "page-{p}.svg"
            code, _, stderr = await _run_typst([*common, str(out), "--format", "svg"])
            if code != 0:
                return CompileResult(ok=False, diagnostics=_clean_diagnostics(stderr, workdir))
            pages = sorted(workdir.glob("page-*.svg"), key=lambda p: int(p.stem.split("-")[1]))
            svgs = [p.read_text(encoding="utf-8") for p in pages]
            return CompileResult(ok=True, svgs=svgs, pages=len(svgs))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def compile_document(
    kind: str,
    template_id: str,
    data: dict,
    doc_settings: dict,
    photo: bytes | None = None,
    fmt: str = "svg",
) -> tuple[CompileResult, str]:
    """Render data -> self-contained source -> compile. The page is exactly as
    tall as its content, so there is nothing to fit. Returns (result, source)."""
    source = render_source(kind, template_id, data, doc_settings, has_photo=photo is not None)
    return await compile_source(source, photo=photo, fmt=fmt), source
