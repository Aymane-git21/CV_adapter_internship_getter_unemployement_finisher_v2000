"""Gate tests for the LaTeX lane's continuous page (texsvc/fit.py) and the
CVGFILL probe parser. The latexc client is replaced with scripted fakes; real
compiles live in services/latexc/tests."""
import json
from pathlib import Path

import pytest

from backend.app.texsvc import fit
from backend.app.texsvc.client import _parse_total
from backend.app.typstsvc.renderer import CompileResult

FIXTURES = Path(__file__).parent / "fixtures"


def _cv_data() -> dict:
    return json.loads((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))


_SETTINGS = {"template": "onyx", "accent": "#C2551B", "density": "normal",
             "show_photo": False, "font_scale": 1.0, "lang": "en",
             "page_mode": "continuous", "compiler": "latex"}


def _script(monkeypatch, outcomes):
    """Each outcome is (pages, total); pages=-1 scripts a failed compile.
    Pops one per compile attempt; returns the list of sources attempted."""
    seen: list[str] = []

    async def fake(doc_id: str, tex: str):
        pages, total = outcomes.pop(0)
        seen.append(tex)
        if pages < 0:
            return CompileResult(ok=False, diagnostics="scripted failure"), tex, None
        return (
            CompileResult(ok=True, pages=pages, pdf=b"%PDF-f", svgs=["<svg/>"] * pages),
            tex,
            total,
        )

    monkeypatch.setattr(fit.client, "compile_tex_measured", fake)
    return seen


async def test_two_pass_trims_to_content(monkeypatch):
    seen = _script(monkeypatch, [(1, 600.0), (1, 600.0)])
    result, source = await fit.compile_tex_document("c1", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 1
    assert len(seen) == 2
    assert "paperheight=500cm" in seen[0], "pass 1 must use the measuring canvas"
    # 600pt content + 2 * 1.1cm margins (62.36pt) + 12pt pad
    assert "paperheight=674.36pt" in seen[1]
    assert source == seen[1]


async def test_probe_lost_serves_pass1(monkeypatch):
    seen = _script(monkeypatch, [(1, None)])
    result, source = await fit.compile_tex_document("c2", _cv_data(), dict(_SETTINGS))
    assert result.ok and len(seen) == 1
    assert "paperheight=500cm" in source


async def test_content_past_canvas_serves_pass1(monkeypatch):
    seen = _script(monkeypatch, [(2, 14000.0)])
    result, _ = await fit.compile_tex_document("c3", _cv_data(), dict(_SETTINGS))
    assert result.ok and result.pages == 2 and len(seen) == 1


async def test_pass2_failure_falls_back(monkeypatch):
    seen = _script(monkeypatch, [(1, 600.0), (-1, None)])
    result, source = await fit.compile_tex_document("c4", _cv_data(), dict(_SETTINGS))
    assert result.ok, "pass-1 page must be served when the trim pass fails"
    assert len(seen) == 2 and source == seen[0]


async def test_pass1_failure_short_circuits(monkeypatch):
    seen = _script(monkeypatch, [(-1, None)])
    result, _ = await fit.compile_tex_document("c5", _cv_data(), dict(_SETTINGS))
    assert not result.ok and result.diagnostics == "scripted failure"
    assert len(seen) == 1, "no trim pass after a failed measuring pass"


async def test_stored_paged_setting_still_renders_continuous(monkeypatch):
    """Documents saved before A4 pagination was removed carry page_mode
    "paged"; the LaTeX lane still trims one continuous page, never A4."""
    seen = _script(monkeypatch, [(1, 600.0), (1, 600.0)])
    _, src = await fit.compile_tex_document(
        "c6", _cv_data(), {**_SETTINGS, "page_mode": "paged"}
    )
    assert "paperheight=500cm" in seen[0]
    assert "paperheight=674.36pt" in src
    assert not any("a4paper" in s for s in seen)


@pytest.mark.parametrize(
    ("tail", "expected"),
    [
        ("CVGFILL:600.5pt/14119.7pt", 600.5),  # huge canvas goal is fine for total
        ("CVGFILL:600.5pt/770.0pt", 600.5),
        ("CVGFILL:abcpt/770.0pt", None),
        ("no probe", None),
    ],
)
def test_parse_total(tail, expected):
    assert _parse_total(tail) == expected
