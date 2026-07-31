"""One-page fitting for the LaTeX lane, mirroring typstsvc.renderer.compile_document.

Overflow tightens density (dropping any font upscale first); underflow grows
font_scale until the page reads full. Thresholds are imported from the Typst
renderer so both engines share one definition of "fits". The fill measure is
the CVGFILL probe tex_onyx types into the compile log (parsed by client);
None fails open, exactly like measure_fill on the Typst side.
"""
from ..typstsvc.renderer import (
    _DENSITIES,
    _FILL_MIN,
    _FILL_TARGET,
    _MAX_FONT_SCALE,
    CompileResult,
)
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
    """Engine entry point: fits to one A4 page, or trims an endless page in
    continuous mode. Mirrors what compile_document does for Typst."""
    if (doc_settings or {}).get("page_mode") == "continuous":
        return await compile_tex_continuous(doc_id, data, doc_settings)
    return await compile_tex_fitted(doc_id, data, doc_settings)


async def compile_tex_continuous(
    doc_id: str, data: dict, doc_settings: dict
) -> tuple[CompileResult, str]:
    """Two-pass endless page: pass 1 typesets on a 500 cm canvas and reads the
    CVGFILL content height from the log; pass 2 recompiles with paperheight
    trimmed to content + margins. Degenerate cases (probe lost, content past
    the canvas, pass-2 failure) serve the pass-1 page, which is already laid
    out correctly, just with trailing whitespace."""

    def _stamp(res: CompileResult) -> CompileResult:
        res.density_used = (doc_settings or {}).get("density", "normal")
        try:
            res.font_scale_used = float((doc_settings or {}).get("font_scale") or 1.0)
        except (TypeError, ValueError):
            res.font_scale_used = 1.0
        return res

    src1 = render_tex(data, doc_settings)
    res1, _s, _fill, total = await client.compile_tex_measured(doc_id, src1)
    if not res1.ok:
        return res1, src1
    if res1.pages > 1 or total is None:
        return _stamp(res1), src1

    density = (doc_settings or {}).get("density", "normal")
    margin_y_cm = _TEX_PARAMS.get(density, _TEX_PARAMS["normal"])["margin_y"]
    height_pt = total + 2 * margin_y_cm * _CM_TO_PT + _TRIM_PAD_PT

    src2 = render_tex(data, doc_settings, page_height_pt=height_pt)
    res2, _s2, _f2, _t2 = await client.compile_tex_measured(doc_id, src2)
    if not res2.ok or res2.pages != 1:
        return _stamp(res1), src1
    return _stamp(res2), src2


async def compile_tex_fitted(
    doc_id: str, data: dict, doc_settings: dict
) -> tuple[CompileResult, str]:
    """Render data -> .tex -> warm compile, fitted to exactly one page.
    Returns (result, final_source); result carries density_used/font_scale_used
    for the same settings write-back the Typst path does."""
    density = doc_settings.get("density", "normal")
    d_idx = _DENSITIES.index(density) if density in _DENSITIES else 0
    try:
        scale = float(doc_settings.get("font_scale") or 1.0)
    except (TypeError, ValueError):
        scale = 1.0
    scale = min(max(scale, 0.8), _MAX_FONT_SCALE)

    async def attempt(d: str, s: float) -> tuple[CompileResult, str, float | None]:
        merged = {**doc_settings, "density": d, "font_scale": s}
        src = render_tex(data, merged)
        res, _src, fill, _total = await client.compile_tex_measured(doc_id, src)
        res.density_used = d
        res.font_scale_used = s
        return res, src, fill

    result, source, fill = await attempt(_DENSITIES[d_idx], scale)
    if not result.ok:
        return result, source

    # ---- overflow: undo any upscale first, then tighten density ------------
    while result.pages > 1 and scale > 1.0:
        scale = max(1.0, round(scale * 0.92, 2))
        result, source, fill = await attempt(_DENSITIES[d_idx], scale)
        if not result.ok:
            return result, source
    while result.pages > 1 and d_idx + 1 < len(_DENSITIES):
        d_idx += 1
        result, source, fill = await attempt(_DENSITIES[d_idx], scale)
        if not result.ok:
            return result, source

    # ---- underflow: grow the type until the page reads full ----------------
    if result.pages == 1:
        for _ in range(3):
            if fill is None or fill >= _FILL_MIN or scale >= _MAX_FONT_SCALE:
                break
            factor = min(_FILL_TARGET / max(fill, 0.3), 1.35)
            scale = min(_MAX_FONT_SCALE, round(scale * factor, 2))
            cand, cand_src, cand_fill = await attempt(_DENSITIES[d_idx], scale)
            if not cand.ok:
                break
            if cand.pages > 1:
                # overshot past one page: back off until it fits again
                while cand.ok and cand.pages > 1 and scale > 1.0:
                    scale = max(1.0, round(scale - 0.06, 2))
                    cand, cand_src, cand_fill = await attempt(_DENSITIES[d_idx], scale)
                if cand.ok and cand.pages == 1:
                    result, source = cand, cand_src
                break
            result, source, fill = cand, cand_src, cand_fill
    return result, source
