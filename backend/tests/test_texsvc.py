"""Gate tests for the deterministic CVData -> LaTeX renderer. Pure string
work: no TeX binary, no network. Real compiles live in services/latexc/tests."""
import re

from backend.app.texsvc.escape import esc
from backend.app.texsvc.tex_onyx import render_tex

from .test_typst import _cv_data


def _settings(**over) -> dict:
    base = {"template": "onyx", "accent": "#C2551B", "density": "normal",
            "show_photo": False, "font_scale": 1.0, "lang": "en",
            "page_mode": "paged", "compiler": "latex"}
    return {**base, **over}


def test_escape_adversarial():
    s = esc("100% & more_ #1 {x} \\ ~^ $5")
    for frag in (r"\%", r"\&", r"\_", r"\#", r"\{", r"\}",
                 r"\textbackslash{}", r"\textasciitilde{}",
                 r"\textasciicircum{}", r"\$"):
        assert frag in s
    assert "\x00" not in esc("a\x00b")


def test_escape_no_double_escape():
    # simultaneous single pass: the backslash expansion must not be re-escaped
    assert esc("\\&") == r"\textbackslash{}\&"


def test_escape_strips_control_and_separator_chars():
    assert esc("a\x07b") == "ab"
    assert esc("a\u2028b") == "a\nb"


def test_render_tex_structure():
    tex = render_tex(_cv_data(), _settings())
    assert tex.startswith("\\documentclass")
    assert "\\definecolor{cvaccent}{HTML}{C2551B}" in tex
    assert "IBM Plex Sans" in tex
    assert "\\begin{document}" in tex and tex.rstrip().endswith("\\end{document}")
    assert "-no-shell-escape" not in tex  # runner flag, never source content


def test_render_tex_no_raw_specials_in_body():
    tex = render_tex(_cv_data(), _settings())
    body = tex.split("\\begin{document}", 1)[1]
    stripped = re.sub(r"\\[A-Za-z]+", "", body)
    for escaped in (r"\&", r"\_", r"\#", r"\%", r"\$"):
        stripped = stripped.replace(escaped, "")
    assert not re.search(r"[&_#$]", stripped), "raw TeX special leaked into body"


def test_render_tex_escapes_user_content():
    data = _cv_data()
    data["full_name"] = "Alex & Sons_ 100% #1"
    tex = render_tex(data, _settings())
    assert r"Alex \& Sons\_ 100\% \#1" in tex


def test_render_tex_bad_accent_falls_back():
    tex = render_tex(_cv_data(), _settings(accent="#zzzzzz"))
    assert "\\definecolor{cvaccent}{HTML}{C2551B}" in tex


def test_render_tex_localized_labels():
    tex = render_tex(_cv_data(), _settings(lang="de"))
    assert "Berufserfahrung" in tex
    tex_fr = render_tex(_cv_data(), _settings(lang="fr"))
    assert "Expérience professionnelle" in tex_fr


def test_render_tex_density_changes_geometry():
    normal = render_tex(_cv_data(), _settings())
    xtight = render_tex(_cv_data(), _settings(density="xtight"))
    assert "top=1.1cm" in normal and "top=0.85cm" in xtight
