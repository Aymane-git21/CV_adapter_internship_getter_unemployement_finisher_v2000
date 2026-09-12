"""Continuous-page compile for the LaTeX lane, the counterpart of
typstsvc.renderer.compile_document.

Every document is one continuous page. TeX cannot size a page to its content
in a single run, so this takes two passes: pass 1 typesets on a 500 cm canvas
and reads the content height from the CVGFILL probe tex_onyx types into the
log; pass 2 recompiles with paperheight trimmed to content + margins.
Degenerate cases (failed or lost probe, content past the canvas, pass-2
failure) serve the pass-1 page, which is laid out correctly, just with
trailing whitespace. A4 pagination and its one-page fit loop were removed
2026-09-12.
"""
from ..typstsvc.renderer import CompileResult
from . import client
from .tex_onyx import _DENSITIES as _TEX_PARAMS
from .tex_onyx import render_tex

_CM_TO_PT = 28.3465
# Covers the final line's depth plus \pagetotal rounding; disappears into the
# bottom margin visually.
_TRIM_PAD_PT = 12.0


async def compile_tex_document(
    doc_id: str, data: dict, doc_settings: dict
) -> tuple[CompileResult, str]:
    """Engine entry point: data -> .tex -> two-pass warm compile, trimmed to
    one continuous page. Returns (result, final_source)."""
    src1 = render_tex(data, doc_settings)
    res1, _s, total = await client.compile_tex_measured(doc_id, src1)
    if not res1.ok or res1.pages > 1 or total is None:
        return res1, src1

    density = (doc_settings or {}).get("density", "normal")
    margin_y_cm = _TEX_PARAMS.get(density, _TEX_PARAMS["normal"])["margin_y"]
    height_pt = total + 2 * margin_y_cm * _CM_TO_PT + _TRIM_PAD_PT

    src2 = render_tex(data, doc_settings, page_height_pt=height_pt)
    res2, _s2, _t2 = await client.compile_tex_measured(doc_id, src2)
    if not res2.ok or res2.pages != 1:
        return res1, src1
    return res2, src2
