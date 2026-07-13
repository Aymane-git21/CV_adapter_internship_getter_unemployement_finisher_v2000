"""Golden compile tests — every template must compile the rich fixture to a
single page, and the source-mode roundtrip must hold."""
import json
import shutil
from pathlib import Path

import pytest

from backend.app.config import get_settings
from backend.app.typstsvc import renderer

FIXTURES = Path(__file__).parent / "fixtures"

typst_missing = shutil.which(get_settings().typst_command) is None and not Path(
    get_settings().typst_command
).exists()
pytestmark = pytest.mark.skipif(typst_missing, reason="typst binary not installed")


def _cv_data() -> dict:
    return json.loads((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))


def _letter_data() -> dict:
    return json.loads((FIXTURES / "sample_letter.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("template", ["onyx", "classic", "compact"])
async def test_cv_templates_compile_one_page(template):
    settings = {"template": template, "accent": "#0F62FE", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en"}
    result, source = await renderer.compile_document("cv", template, _cv_data(), settings, fmt="svg")
    assert result.ok, result.diagnostics
    assert result.pages == 1
    assert result.svgs and result.svgs[0].startswith("<svg")
    assert "#import \"/typst/" in source


@pytest.mark.parametrize("lang", ["en", "fr", "de"])
async def test_cv_compiles_in_all_ui_languages(lang):
    settings = {"template": "onyx", "accent": "#C2551B", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": lang}
    result, source = await renderer.compile_document("cv", "onyx", _cv_data(), settings, fmt="svg")
    assert result.ok, result.diagnostics
    assert result.pages == 1
    assert f'lang: "{lang}"' in source


async def test_letter_compiles_pdf():
    settings = {"template": "classic", "accent": "#1C3B5A", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en"}
    result, _ = await renderer.compile_document("letter", "classic", _letter_data(), settings, fmt="pdf")
    assert result.ok, result.diagnostics
    assert result.pdf and result.pdf.startswith(b"%PDF")


async def test_source_roundtrip_and_edit():
    settings = {"template": "onyx", "accent": "#7C3AED", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "fr"}
    source = renderer.render_source("cv", "onyx", _cv_data(), settings, has_photo=False)
    result = await renderer.compile_source(source, fmt="svg")
    assert result.ok, result.diagnostics
    # A user edit on the literal must survive recompilation.
    # (SVG text is glyph outlines, so compare structure, not strings.)
    edited = source.replace('"Alex Martin"', '"Alexandra Martine-Dupont"')
    result2 = await renderer.compile_source(edited, fmt="svg")
    assert result2.ok, result2.diagnostics
    assert result2.pages == 1
    assert result2.svgs[0] != result.svgs[0]  # the longer name changed the layout


async def test_compile_error_reports_diagnostics():
    bad = '#import "/typst/cv_onyx.typ": render\n#render(json("nope.json"), (:), photo: none)\n'
    result = await renderer.compile_source(bad, fmt="svg")
    assert not result.ok
    assert "error" in result.diagnostics.lower()


async def test_density_fallback_squeezes_long_cv():
    data = _cv_data()
    data["experience"] = data["experience"] * 4  # force overflow at normal density
    settings = {"template": "onyx", "accent": "#0F62FE", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en"}
    result, _ = await renderer.compile_document("cv", "onyx", data, settings, fmt="svg")
    assert result.ok
    assert result.density_used in ("tight", "xtight")


def _sparse_cv() -> dict:
    """A thin CV that condenses at the top of the page at scale 1.0."""
    data = _cv_data()
    data["experience"] = data["experience"][:1]
    data["experience"][0]["bullets"] = data["experience"][0]["bullets"][:2]
    data["education"] = data["education"][:1]
    data["projects"] = []
    data["certifications"] = []
    data["interests"] = []
    return data


async def test_sparse_cv_upscales_to_fill_page():
    settings = {"template": "onyx", "accent": "#C2551B", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en"}
    result, source = await renderer.compile_document("cv", "onyx", _sparse_cv(), settings, fmt="svg")
    assert result.ok, result.diagnostics
    assert result.pages == 1
    assert result.font_scale_used > 1.0
    fill = await renderer.measure_fill(source)
    assert fill is not None
    # The fill loop targets 0.92 but caps font_scale at 1.5; a truly tiny CV
    # can't reach the floor, so assert real improvement over the unscaled page.
    base_src = renderer.render_source(
        "cv", "onyx", _sparse_cv(), {**settings, "font_scale": 1.0}, has_photo=False
    )
    base_fill = await renderer.measure_fill(base_src)
    assert base_fill is not None
    assert fill > base_fill + 0.05


async def test_fill_pass_respects_already_full_pages():
    """The fill pass only engages on underfull pages: an already-full page
    keeps scale 1.0, an underfull one is scaled up and ends fuller."""
    data = _cv_data()
    settings = {"template": "onyx", "accent": "#0F62FE", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en"}
    base_src = renderer.render_source("cv", "onyx", data, settings, has_photo=False)
    base_fill = await renderer.measure_fill(base_src)
    assert base_fill is not None

    result, source = await renderer.compile_document("cv", "onyx", data, settings, fmt="svg")
    assert result.ok
    assert result.pages == 1
    if base_fill >= 0.80:
        assert result.font_scale_used == 1.0
    else:
        assert result.font_scale_used > 1.0
        final_fill = await renderer.measure_fill(source)
        assert final_fill is not None and final_fill > base_fill


async def test_measure_fill_orders_documents():
    settings = {"template": "onyx", "accent": "#0F62FE", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en"}
    sparse_src = renderer.render_source("cv", "onyx", _sparse_cv(), settings, has_photo=False)
    rich_src = renderer.render_source("cv", "onyx", _cv_data(), settings, has_photo=False)
    sparse_fill = await renderer.measure_fill(sparse_src)
    rich_fill = await renderer.measure_fill(rich_src)
    assert sparse_fill is not None and rich_fill is not None
    assert 0.05 < sparse_fill < rich_fill <= 1.0


async def test_measure_fill_fails_open_on_bad_source():
    assert await renderer.measure_fill("#broken(") is None


def test_typst_literal_escaping():
    src = renderer.typst_literal({"a": 'He said "hi"\nnewline \\ backslash', "b": [1, True, None]})
    assert '\\"hi\\"' in src
    assert "\\n" in src
    assert "true" in src and "none" in src
