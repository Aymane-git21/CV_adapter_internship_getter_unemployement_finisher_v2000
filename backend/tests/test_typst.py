"""Golden compile tests — every template must compile the rich fixture to a
single continuous page, and the source-mode roundtrip must hold."""
import json
import re
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

_A4_PT = 841.89


def _cv_data() -> dict:
    return json.loads((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))


def _letter_data() -> dict:
    return json.loads((FIXTURES / "sample_letter.json").read_text(encoding="utf-8"))


def _svg_height(svg: str) -> float:
    m = re.search(r'height="([0-9.]+)pt"', svg)
    assert m, "svg carries no pt height"
    return float(m.group(1))


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


@pytest.mark.parametrize("template", ["onyx", "classic", "compact"])
async def test_contact_row_overflow_splits_not_crashes(template):
    """contact-row balances overflowing contact lines into two rows; both the
    overflow branch (long values) and the single-line branch (short values)
    must compile to one page."""
    settings = {"template": template, "accent": "#0F62FE", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "fr"}
    long_data = _cv_data()
    long_data["contacts"] = {
        "email": "aymanemerbouh03.professional@gmail.com",
        "phone": "+33 6 12 34 56 78",
        "location": "Toulouse, Occitanie, France",
        "linkedin": "linkedin.com/in/aymane-merbouh-prompt-engineering",
        "github": "github.com/aymane-merbouh",
        "website": "cvglowup-portfolio-1057358093.europe-west1.run.app",
    }
    result, _ = await renderer.compile_document("cv", template, long_data, settings, fmt="svg")
    assert result.ok, result.diagnostics
    assert result.pages == 1

    short_data = _cv_data()
    short_data["contacts"] = {"email": "a@b.fr", "location": "Paris"}
    result2, _ = await renderer.compile_document("cv", template, short_data, settings, fmt="svg")
    assert result2.ok, result2.diagnostics
    assert result2.pages == 1


def _sparse_cv() -> dict:
    """A thin CV whose content ends well before an A4 sheet would."""
    data = _cv_data()
    data["experience"] = data["experience"][:1]
    data["experience"][0]["bullets"] = data["experience"][0]["bullets"][:2]
    data["education"] = data["education"][:1]
    data["projects"] = []
    data["certifications"] = []
    data["interests"] = []
    return data


def test_density_spacing_rhythm_keeps_bullets_separated():
    """Guards the 2026-07 "crammed page" regression: at every density the
    visual gap BETWEEN bullets (leading + bullet-gap) must be clearly larger
    than the line gap INSIDE a wrapped bullet (leading alone), and the
    hierarchy bullet < entry < section must hold. With the old constants
    (normal bullet-gap 2.2pt vs 6.2pt line gap, ratio 1.35) bullets fused
    into a wall of text; the retune keeps the ratio >= 1.45."""
    import re

    from backend.app.config import get_settings

    src = (get_settings().templates_dir / "typst" / "common.typ").read_text(encoding="utf-8")
    rows = re.findall(
        r"base: ([\d.]+)pt.*?leading: ([\d.]+)em.*?"
        r"sect-above: ([\d.]+)pt, sect-below: [\d.]+pt, "
        r"entry-gap: ([\d.]+)pt, bullet-gap: ([\d.]+)pt",
        src,
        re.S,
    )
    assert len(rows) == 3, "expected the three density parameter sets"
    for base, leading, sect_above, entry_gap, bullet_gap in ((float(v) for v in r) for r in rows):
        line_gap = leading * base
        assert (line_gap + bullet_gap) / line_gap >= 1.45, "bullets fuse with wrapped lines"
        assert bullet_gap < entry_gap < sect_above, "spacing hierarchy inverted"


def test_typst_literal_escaping():
    src = renderer.typst_literal({"a": 'He said "hi"\nnewline \\ backslash', "b": [1, True, None]})
    assert '\\"hi\\"' in src
    assert "\\n" in src
    assert "true" in src and "none" in src


# ---- page layout: one continuous page, as tall as its content ---------------


@pytest.mark.parametrize("template", ["onyx", "classic", "compact"])
async def test_long_cv_grows_one_tall_page(template):
    data = _cv_data()
    data["experience"] = data["experience"] * 4  # far past one A4 sheet
    settings = {"template": template, "accent": "#C2551B", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en"}
    result, _ = await renderer.compile_document("cv", template, data, settings, fmt="svg")
    assert result.ok, result.diagnostics
    assert result.pages == 1, "a long CV must grow its page, never paginate"
    assert _svg_height(result.svgs[0]) > _A4_PT, "page did not grow past A4"


@pytest.mark.parametrize("template", ["onyx", "classic", "compact"])
async def test_short_cv_page_ends_with_its_content(template):
    settings = {"template": template, "accent": "#C2551B", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en"}
    result, _ = await renderer.compile_document("cv", template, _sparse_cv(), settings, fmt="svg")
    assert result.ok, result.diagnostics
    assert result.pages == 1
    assert _svg_height(result.svgs[0]) < _A4_PT - 100, "a sparse CV kept a full A4 sheet"


async def test_stored_paged_setting_still_renders_continuous():
    """Documents saved before A4 pagination was removed carry page_mode
    "paged" in their settings and embedded sources; the templates ignore it."""
    settings = {"template": "onyx", "accent": "#0F62FE", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en", "page_mode": "paged"}
    result, _ = await renderer.compile_document("cv", "onyx", _sparse_cv(), settings, fmt="svg")
    assert result.ok, result.diagnostics
    assert result.pages == 1
    assert _svg_height(result.svgs[0]) < _A4_PT - 100, "legacy paged setting brought A4 back"


async def test_letter_is_one_continuous_page():
    settings = {"template": "classic", "accent": "#1C3B5A", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en", "page_mode": "paged"}
    result, _ = await renderer.compile_document(
        "letter", "classic", _letter_data(), settings, fmt="svg")
    assert result.ok, result.diagnostics
    assert result.pages == 1
    assert abs(_svg_height(result.svgs[0]) - _A4_PT) > 0.5, "letter still sized to A4"
