"""Gate tests for the LaTeX one-page fit loop (texsvc/fit.py) and the CVGFILL
probe parser. The latexc client is replaced with scripted fakes; real compiles
live in services/latexc/tests."""
import json
from pathlib import Path

import pytest

from backend.app.texsvc import fit
from backend.app.texsvc.client import _parse_fill
from backend.app.typstsvc.renderer import CompileResult

FIXTURES = Path(__file__).parent / "fixtures"


def _cv_data() -> dict:
    return json.loads((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))


_SETTINGS = {"template": "onyx", "accent": "#C2551B", "density": "normal",
             "show_photo": False, "font_scale": 1.0, "lang": "en",
             "page_mode": "paged", "compiler": "latex"}


def _script(monkeypatch, outcomes):
    """Each outcome is (pages, fill); pops one per compile attempt."""
    seen: list[str] = []

    async def fake(doc_id: str, tex: str):
        pages, fill = outcomes.pop(0)
        seen.append(tex)
        return CompileResult(ok=True, pages=pages, pdf=b"%PDF-f", svgs=["<svg/>"] * pages), tex, fill

    monkeypatch.setattr(fit.client, "compile_tex_measured", fake)
    return seen


async def test_overflow_tightens_density(monkeypatch):
    outcomes = [(2, None), (2, None), (1, 0.94)]  # normal, tight, xtight
    seen = _script(monkeypatch, outcomes)
    result, source = await fit.compile_tex_fitted("d1", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 1
    assert result.density_used == "xtight"
    assert len(seen) == 3
    assert source == seen[-1]


async def test_underflow_upscales_font(monkeypatch):
    outcomes = [(1, 0.55), (1, 0.93)]
    _script(monkeypatch, outcomes)
    result, _ = await fit.compile_tex_fitted("d2", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 1
    assert result.density_used == "normal"
    assert result.font_scale_used > 1.0


async def test_upscale_overshoot_backs_off(monkeypatch):
    outcomes = [(1, 0.55), (2, None), (1, 0.9)]
    _script(monkeypatch, outcomes)
    result, _ = await fit.compile_tex_fitted("d3", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 1


async def test_fill_probe_missing_fails_open(monkeypatch):
    outcomes = [(1, None)]
    seen = _script(monkeypatch, outcomes)
    result, _ = await fit.compile_tex_fitted("d4", _cv_data(), dict(_SETTINGS))
    assert result.ok and len(seen) == 1, "no fill signal -> no extra attempts"
    assert result.font_scale_used == 1.0


async def test_compile_failure_short_circuits(monkeypatch):
    async def fake(doc_id: str, tex: str):
        return CompileResult(ok=False, diagnostics="boom"), tex, None

    monkeypatch.setattr(fit.client, "compile_tex_measured", fake)
    result, _ = await fit.compile_tex_fitted("d5", _cv_data(), dict(_SETTINGS))
    assert not result.ok and result.diagnostics == "boom"


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
