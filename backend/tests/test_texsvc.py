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


def _body(tex: str) -> str:
    return tex.split(r"\begin{document}", 1)[1]


def _preamble(tex: str) -> str:
    return tex.split(r"\begin{document}", 1)[0]


def _luminance(hex_rgb: str) -> float:
    def chan(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_rgb[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast_on_white(hex_rgb: str) -> float:
    return 1.05 / (_luminance(hex_rgb) + 0.05)


def test_contact_items_are_individually_unbreakable():
    """The spaces inside a phone number used to be the only legal break in the
    contact row, so TeX wrapped mid-number. Each item gets its own \\mbox."""
    data = _cv_data()
    data["contacts"]["phone"] = "+33 6 12 34 56 78"
    tex = render_tex(data, _settings())
    assert r"\mbox{+33 6 12 34 56 78}" in tex
    assert r"\mbox{\href{mailto:" in tex


def test_overlong_contact_value_stays_breakable():
    """An \\mbox wider than the measure overflows into the margin, so past the
    threshold the value keeps its break opportunities."""
    data = _cv_data()
    data["contacts"]["website"] = "example.com/" + "x" * 80
    tex = render_tex(data, _settings())
    assert r"\mbox{\href{https://example.com/" not in tex
    assert r"\href{https://example.com/" in tex


def test_separators_do_not_rely_on_collapsing_spaces():
    """LaTeX collapses runs of spaces, so the "a  ·  b" joins rendered as
    "a · b" and the intended gap silently disappeared."""
    body = _body(render_tex(_cv_data(), _settings()))
    assert "  ·  " not in body
    assert r"\cvdot{}" in body


def test_separators_break_after_the_dot_never_before():
    """\\cvsep/\\cvdot own the only breakpoint in a run of items: sealed before
    the dot, open after it. Without the trailing glue an \\mbox-ed contact row
    would have no legal break at all and would run off the page."""
    preamble = _preamble(render_tex(_cv_data(), _settings()))
    code = "\n".join(
        ln for ln in preamble.splitlines() if not ln.lstrip().startswith("%")
    )
    for macro in (r"\cvsep", r"\cvdot"):
        m = re.search(re.escape(macro) + r"\}\{(\\nobreak\\hspace\{[\d.]+pt\})", code)
        assert m, f"{macro} must open with \\nobreak + gap"
    assert r"\enspace" not in code, "\\enspace is a kern: it offers no breakpoint"


def test_body_greys_meet_wcag_aa_on_white():
    """cvfaint carries locations and project tech stacks, which is real content,
    so it has to clear 4.5:1 like the rest of the body text."""
    tex = render_tex(_cv_data(), _settings())
    greys = dict(re.findall(r"\\definecolor\{(cv\w+)\}\{HTML\}\{([0-9A-F]{6})\}", tex))
    for name in ("cvink", "cvmuted", "cvfaint"):
        ratio = _contrast_on_white(greys[name])
        assert ratio >= 4.5, f"{name} #{greys[name]} is only {ratio:.2f}:1 on white"
    # the hierarchy still has to read: faint stays lighter than muted
    assert _contrast_on_white(greys["cvfaint"]) < _contrast_on_white(greys["cvmuted"])


def test_projects_and_education_use_macros():
    body = _body(render_tex(_cv_data(), _settings()))
    assert r"\cvprojectfirst{" in body and r"\cvproject{" in body
    assert r"\cvdetail{" in body
    assert r"\noindent{\szbase\bfseries" not in body, "hand-rolled entry markup"


def test_first_bullet_is_welded_to_its_entry_head():
    data = _cv_data()
    body = _body(render_tex(data, _settings()))
    assert body.count(r"\cvbulletfirst{") >= len(data["experience"])
    assert r"\cvbullet{" in body, "later bullets must stay breakable"


def test_entry_heads_do_not_weld_to_the_next_block():
    """A \\nobreak before vertical glue removes the breakpoint AT that glue, so
    a head ending in \\nobreak welds to whatever follows it. With no bullets in
    between that cascaded entry -> entry -> section into one unbreakable run and
    forced an early page break. Heads must end on a bare \\par; only the first
    bullet and the detail line seal their own leading gap."""
    preamble = _preamble(render_tex(_cv_data(), _settings()))
    assert r"\par\nobreak}" not in preamble
    assert r"\newcommand{\cvbulletfirst}[1]{\par\nobreak\vspace" in preamble
    assert r"\newcommand{\cvdetail}[1]{\par\nobreak\vspace" in preamble


def test_widow_and_orphan_control_is_on():
    """A two-line bullet split across pages left one line stranded."""
    preamble = _preamble(render_tex(_cv_data(), _settings()))
    assert r"\widowpenalty=10000" in preamble
    assert r"\clubpenalty=10000" in preamble
