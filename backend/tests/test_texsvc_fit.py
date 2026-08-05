"""Gate tests for the LaTeX one-page fit loop (texsvc/fit.py) and the CVGFILL
probe parser. The latexc client is replaced with scripted fakes; real compiles
live in services/latexc/tests."""
import json
from pathlib import Path

import pytest

from backend.app.texsvc import fit
from backend.app.texsvc.client import _parse_fill, _parse_total
from backend.app.typstsvc.renderer import CompileResult

FIXTURES = Path(__file__).parent / "fixtures"


def _cv_data() -> dict:
    return json.loads((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))


_SETTINGS = {"template": "onyx", "accent": "#C2551B", "density": "normal",
             "show_photo": False, "font_scale": 1.0, "lang": "en",
             "page_mode": "paged", "compiler": "latex"}


def _script(monkeypatch, outcomes):
    """Each outcome is (pages, fill, total); pages=-1 scripts a failed compile.
    Pops one per compile attempt; returns the list of sources attempted."""
    seen: list[str] = []

    async def fake(doc_id: str, tex: str):
        pages, fill, total = outcomes.pop(0)
        seen.append(tex)
        if pages < 0:
            return CompileResult(ok=False, diagnostics="scripted failure"), tex, None, None
        return (
            CompileResult(ok=True, pages=pages, pdf=b"%PDF-f", svgs=["<svg/>"] * pages),
            tex,
            fill,
            total,
        )

    monkeypatch.setattr(fit.client, "compile_tex_measured", fake)
    return seen


async def test_overflow_tightens_density(monkeypatch):
    outcomes = [(2, None, None), (2, None, None), (1, 0.94, None)]  # normal, tight, xtight
    seen = _script(monkeypatch, outcomes)
    result, source = await fit.compile_tex_fitted("d1", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 1
    assert result.density_used == "xtight"
    assert len(seen) == 3
    assert source == seen[-1]


async def test_underflow_upscales_font(monkeypatch):
    outcomes = [(1, 0.55, None), (1, 0.93, None)]
    _script(monkeypatch, outcomes)
    result, _ = await fit.compile_tex_fitted("d2", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 1
    assert result.density_used == "normal"
    assert result.font_scale_used > 1.0


async def test_upscale_overshoot_backs_off(monkeypatch):
    outcomes = [(1, 0.55, None), (2, None, None), (1, 0.9, None)]
    _script(monkeypatch, outcomes)
    result, _ = await fit.compile_tex_fitted("d3", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 1


async def test_fill_probe_missing_fails_open(monkeypatch):
    outcomes = [(1, None, None)]
    seen = _script(monkeypatch, outcomes)
    result, _ = await fit.compile_tex_fitted("d4", _cv_data(), dict(_SETTINGS))
    assert result.ok and len(seen) == 1, "no fill signal -> no extra attempts"
    assert result.font_scale_used == 1.0


async def test_overflow_shrinks_type_once_densities_run_out(monkeypatch):
    """normal/tight/xtight all overflow, then the type steps down 0.96, 0.92,
    0.90. Before this rung the loop gave up at xtight and served two pages."""
    outcomes = [(2, None, None)] * 5 + [(1, 0.97, None)]
    seen = _script(monkeypatch, outcomes)
    result, _ = await fit.compile_tex_fitted("d6", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 1
    assert result.density_used == "xtight"
    assert result.font_scale_used == 0.9
    assert not result.overflowed
    assert len(seen) == 6


async def test_overflow_past_every_lever_is_reported(monkeypatch):
    """The readable floor is a floor: below it the honest answer is that the
    content does not fit, not a two-page PDF that pretends it did."""
    _script(monkeypatch, [(2, None, None)] * 6)
    result, _ = await fit.compile_tex_fitted("d7", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 2
    assert result.overflowed
    assert result.font_scale_used == 0.9


async def test_fitting_cv_is_never_flagged_as_overflowed(monkeypatch):
    _script(monkeypatch, [(1, 0.95, None)])
    result, _ = await fit.compile_tex_fitted("d8", _cv_data(), dict(_SETTINGS))
    assert result.ok and not result.overflowed


async def test_compile_failure_short_circuits(monkeypatch):
    async def fake(doc_id: str, tex: str):
        return CompileResult(ok=False, diagnostics="boom"), tex, None, None

    monkeypatch.setattr(fit.client, "compile_tex_measured", fake)
    result, _ = await fit.compile_tex_fitted("d5", _cv_data(), dict(_SETTINGS))
    assert not result.ok and result.diagnostics == "boom"


_CONT = {**_SETTINGS, "page_mode": "continuous"}


async def test_continuous_two_pass_trims_to_content(monkeypatch):
    seen = _script(monkeypatch, [(1, None, 600.0), (1, None, 600.0)])
    result, source = await fit.compile_tex_continuous("c1", _cv_data(), dict(_CONT))
    assert result.ok and result.pages == 1
    assert len(seen) == 2
    assert "paperheight=500cm" in seen[0], "pass 1 must use the measuring canvas"
    # 600pt content + 2 * 1.1cm margins (62.36pt) + 12pt pad
    assert "paperheight=674.36pt" in seen[1]
    assert source == seen[1]
    assert result.density_used == "normal" and result.font_scale_used == 1.0


async def test_continuous_probe_lost_serves_pass1(monkeypatch):
    seen = _script(monkeypatch, [(1, None, None)])
    result, source = await fit.compile_tex_continuous("c2", _cv_data(), dict(_CONT))
    assert result.ok and len(seen) == 1
    assert "paperheight=500cm" in source


async def test_continuous_content_past_canvas_serves_pass1(monkeypatch):
    seen = _script(monkeypatch, [(2, None, 14000.0)])
    result, _ = await fit.compile_tex_continuous("c3", _cv_data(), dict(_CONT))
    assert result.ok and result.pages == 2 and len(seen) == 1


async def test_continuous_pass2_failure_falls_back(monkeypatch):
    seen = _script(monkeypatch, [(1, None, 600.0), (-1, None, None)])
    result, source = await fit.compile_tex_continuous("c4", _cv_data(), dict(_CONT))
    assert result.ok, "pass-1 page must be served when the trim pass fails"
    assert len(seen) == 2 and source == seen[0]


async def test_dispatcher_routes_by_page_mode(monkeypatch):
    seen = _script(monkeypatch, [(1, None, 600.0), (1, None, 600.0)])
    await fit.compile_tex_document("c5", _cv_data(), dict(_CONT))
    assert "paperheight=500cm" in seen[0]

    seen2 = _script(monkeypatch, [(1, 0.95, None)])
    _, src = await fit.compile_tex_document("c6", _cv_data(), dict(_SETTINGS))
    assert "a4paper" in seen2[0] and "paperheight" not in src


@pytest.mark.parametrize(
    ("tail", "expected"),
    [
        ("... CVGFILL:600.0pt/770.0pt ...", pytest.approx(0.779, abs=0.001)),
        ("CVGFILL:800.0pt/770.0pt", 1.0),  # clamped
        ("CVGFILL:10.0pt/16383.99998pt", None),  # maxdimen goal -> unusable
        ("no probe line here", None),
        ("CVGFILL:abcpt/770.0pt", None),
    ],
)
def test_parse_fill(tail, expected):
    assert _parse_fill(tail) == expected


@pytest.mark.parametrize(
    ("tail", "expected"),
    [
        ("CVGFILL:600.5pt/14119.7pt", 600.5),  # huge canvas goal is fine for total
        ("CVGFILL:600.5pt/770.0pt", 600.5),
        ("no probe", None),
    ],
)
def test_parse_total(tail, expected):
    assert _parse_total(tail) == expected
