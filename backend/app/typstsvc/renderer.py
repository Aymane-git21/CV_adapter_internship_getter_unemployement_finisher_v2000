"""Typst rendering service.

Design notes:
- Documents are SELF-CONTAINED Typst sources: the data is embedded as a Typst
  dict literal, so what the user sees in the source editor is the whole truth
  and is directly editable (the Overleaf feel).
- Compiles run inside {templates_dir}/.compile/<uuid>/ with --root set to the
  templates dir. That jail means user-edited source can only read() template
  files and its own data/photo — never .env or anything else.
- One-page fitting, both directions: CVs that overflow are retried at tighter
  densities (dropping any font upscale first); CVs that leave the bottom of
  the page empty are retried with a larger font_scale until the page reads
  full. Underfull detection asks Typst itself (`typst query` on an appended
  end-of-content marker) instead of guessing from the SVG.
"""
import asyncio
import json
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..config import get_settings

_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
_DENSITIES = ["normal", "tight", "xtight"]

# A4 page height in pt; fill = content-end y / page height.
_PAGE_H_PT = 841.89
_FILL_MIN = 0.80     # below this the page reads visibly empty -> scale up
_FILL_TARGET = 0.92  # aim the content end here when upscaling
_MAX_FONT_SCALE = 1.5

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
    density_used: str = "normal"
    font_scale_used: float = 1.0


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


async def measure_fill(source: str, photo: bytes | None = None) -> float | None:
    """How much of the (last) page the content occupies, 0..1.

    Every CV template drops an invisible <cvg-end> anchor (common.typ
    end-anchor()) at the end of its content; `typst query` reads its page/y.
    Returns None when the anchor is missing or the query fails; callers treat
    that as "don't adjust". Content that spills past page 1 reports 1.0.
    """
    settings = get_settings()
    jail_root = settings.templates_dir
    workdir = jail_root / ".compile" / uuid.uuid4().hex
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        (workdir / "main.typ").write_text(source, encoding="utf-8")
        if photo is not None:
            (workdir / "photo.jpg").write_bytes(photo)
        async with _sem():
            code, stdout, _ = await _run_typst([
                "query",
                str(workdir / "main.typ"),
                "<cvg-end>",
                "--root",
                str(jail_root),
                "--font-path",
                str(jail_root / "typst" / "fonts"),
                "--field",
                "value",
                "--one",
            ])
        if code != 0:
            return None
        value = json.loads(stdout)
        if int(value.get("page", 1)) > 1:
            return 1.0
        return min(1.0, float(value["y"]) / _PAGE_H_PT)
    except (ValueError, KeyError, TypeError):
        return None
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def compile_document(
    kind: str,
    template_id: str,
    data: dict,
    doc_settings: dict,
    photo: bytes | None = None,
    fmt: str = "svg",
    fit_one_page: bool = True,
) -> tuple[CompileResult, str]:
    """Render data -> source -> compile, fitting CVs to exactly one FULL page:
    overflow tightens density (dropping any font upscale first), underflow
    grows font_scale until the content reaches the bottom of the sheet.
    Returns (result, final_source)."""
    density = doc_settings.get("density", "normal")
    d_idx = _DENSITIES.index(density) if density in _DENSITIES else 0
    try:
        scale = float(doc_settings.get("font_scale") or 1.0)
    except (TypeError, ValueError):
        scale = 1.0
    scale = min(max(scale, 0.8), _MAX_FONT_SCALE)

    async def attempt(d: str, s: float) -> tuple[CompileResult, str]:
        merged = {**doc_settings, "density": d, "font_scale": s}
        src = render_source(kind, template_id, data, merged, has_photo=photo is not None)
        res = await compile_source(src, photo=photo, fmt="svg")
        res.density_used = d
        res.font_scale_used = s
        return res, src

    result, source = await attempt(_DENSITIES[d_idx], scale)

    if kind == "cv" and fit_one_page and result.ok:
        # ---- overflow: undo any upscale first, then tighten density --------
        while result.pages > 1 and scale > 1.0:
            scale = max(1.0, round(scale * 0.92, 2))
            result, source = await attempt(_DENSITIES[d_idx], scale)
            if not result.ok:
                return result, source
        while result.pages > 1 and d_idx + 1 < len(_DENSITIES):
            d_idx += 1
            result, source = await attempt(_DENSITIES[d_idx], scale)
            if not result.ok:
                return result, source

        # ---- underflow: grow the type until the page reads full ------------
        if result.pages == 1:
            fill = await measure_fill(source, photo)
            for _ in range(3):
                if fill is None or fill >= _FILL_MIN or scale >= _MAX_FONT_SCALE:
                    break
                # Spacing gaps are fixed pt (only type scales), so the naive
                # linear factor undershoots; the loop converges the rest.
                factor = min(_FILL_TARGET / max(fill, 0.3), 1.35)
                scale = min(_MAX_FONT_SCALE, round(scale * factor, 2))
                cand, cand_src = await attempt(_DENSITIES[d_idx], scale)
                if not cand.ok:
                    break
                if cand.pages > 1:
                    # overshot past one page: back off until it fits again
                    while cand.ok and cand.pages > 1 and scale > 1.0:
                        scale = max(1.0, round(scale - 0.06, 2))
                        cand, cand_src = await attempt(_DENSITIES[d_idx], scale)
                    if cand.ok and cand.pages == 1:
                        result, source = cand, cand_src
                    break
                result, source = cand, cand_src
                fill = await measure_fill(source, photo)

    if fmt == "pdf" and result.ok:
        pdf_result = await compile_source(source, photo=photo, fmt="pdf")
        pdf_result.density_used = result.density_used
        pdf_result.font_scale_used = result.font_scale_used
        pdf_result.pages = result.pages
        return pdf_result, source
    return result, source
