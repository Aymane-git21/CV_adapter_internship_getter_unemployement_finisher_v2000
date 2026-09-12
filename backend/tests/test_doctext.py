"""Gate tests for doctext: the text keyword scoring reads must not depend on
which editor produced a document, and must follow real edits in each."""
import json
from pathlib import Path

from backend.app import ats, doctext
from backend.app.schemas import CVData, Keyword
from backend.app.texsvc.tex_onyx import render_tex
from backend.app.typstsvc import renderer

FIXTURES = Path(__file__).parent / "fixtures"
_SETTINGS = {"template": "onyx", "accent": "#0F62FE", "density": "normal",
             "show_photo": False, "font_scale": 1.0, "lang": "en",
             "page_mode": "continuous", "compiler": "typst"}


def _cv() -> dict:
    raw = json.loads((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))
    return CVData.model_validate(raw).model_dump()


def _tricky_cv() -> dict:
    """Strings that break naive extraction: quotes, backslashes, CRs, comment
    and bracket lookalikes inside strings, empties, non-Latin text."""
    cv = _cv()
    cv["summary"] = (
        'Said "ship it" \\ twice\r\nthen // not a comment /* nor this */ '
        "(parens) [brackets] {braces}"
    )
    cv["skills"] = [{"category": "Stack", "items": ["C++", "C#", ".NET", "R&D", "CI/CD",
                                                   "Straße", "ingénierie", ""]}]
    cv["interests"] = ["  ", "tab\there", "日本語", "\r"]
    return cv


def test_cv_text_collects_every_string_leaf_in_order():
    data = {"a": "one", "b": ["two", "", {"c": "three"}], "n": 3, "t": True,
            "z": None, "r": "x\ry", "cr": "\r"}
    assert doctext.cv_text(data) == "one\ntwo\nthree\nxy"


def test_typst_source_text_equals_data_text():
    """The invariant that keeps a switch to the source editor from moving the
    score by itself."""
    for data in (_cv(), _tricky_cv()):
        for has_photo in (False, True):
            source = renderer.render_source("cv", "onyx", data, _SETTINGS, has_photo=has_photo)
            assert doctext.typst_source_text(source) == doctext.cv_text(data)


def test_typst_source_text_excludes_settings_import_and_photo():
    data = {"full_name": "Alex", "skills": [{"category": "Tools", "items": ["Docker"]}]}
    settings = {**_SETTINGS, "accent": "Python", "template": "Golang"}
    source = renderer.render_source("cv", "onyx", data, settings, has_photo=True)
    assert doctext.typst_source_text(source) == "Alex\nTools\nDocker"


def test_typst_source_text_follows_hand_edits_and_skips_comments():
    source = renderer.render_source("cv", "onyx", _cv(), _SETTINGS, has_photo=False)
    edited = source.replace(
        "#let data = (",
        '#let data = (\n  // "Zanzibarware" in a line comment\n  /* "Quuxlang" */',
        1,
    ).replace('"Alex Martin"', '"Alex Martin, Rustacean"')
    assert edited != source and "Rustacean" in edited
    text = doctext.typst_source_text(edited)
    assert "Rustacean" in text
    assert "Zanzibarware" not in text and "Quuxlang" not in text


def test_typst_source_text_decodes_unicode_escapes():
    source = '#let data = (full_name: "Caf\\u{e9} \\u{1F600} \\u{zz}")\n'
    # A malformed \u{..} keeps its characters instead of eating the string.
    assert doctext.typst_source_text(source) == "Caf\u00e9 \U0001F600 u{zz}"


def test_typst_source_text_falls_back_without_a_data_block():
    source = (
        '#import "/typst/cv_onyx.typ": render\n'
        '#let settings = (accent: "Golang", nested: ("Elixir",))\n'
        '#render((full_name: "Alex", headline: "Kotlin dev"), settings, photo: none)\n'
    )
    text = doctext.typst_source_text(source)
    assert text == "Alex\nKotlin dev"


def test_data_block_that_is_not_a_literal_does_not_swallow_the_file():
    source = '#let data = none\n#let other = ("Scala",)\n'
    assert doctext.typst_source_text(source) == ""


def test_tex_source_text_reads_the_rendered_cv():
    tex = render_tex(_tricky_cv(), {**_SETTINGS, "compiler": "latex"})
    text = doctext.tex_source_text(tex)
    for term in ("C++", "C#", "R&D", "CI/CD", "ingénierie", "Straße", ".NET"):
        assert ats.score([Keyword(term=term)], text)["score"] == 100, term
    assert "documentclass" not in text and "usepackage" not in text
    assert "\\" not in text, "a control sequence survived"


def test_tex_source_text_drops_comments_but_keeps_escaped_percent():
    tex = "\\begin{document}\nGrew revenue 30\\% % Hadoop in a comment\n\\textbf{Spark}\\\\ Go\n\\end{document}"
    text = doctext.tex_source_text(tex)
    assert "30%" in text and "Spark" in text and "Go" in text
    assert "Hadoop" not in text and "textbf" not in text
