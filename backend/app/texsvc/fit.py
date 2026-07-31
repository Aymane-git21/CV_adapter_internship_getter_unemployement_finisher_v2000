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
from .tex_onyx import render_tex


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
        res, _src, fill = await client.compile_tex_measured(doc_id, src)
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
