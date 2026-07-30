"""Deterministic CVData -> XeLaTeX source, porting templates/typst/cv_onyx.typ.

Same contract as the Typst path: the LLM never writes markup, every user
string passes through esc(). Density tuples and section labels are copied
from templates/typst/common.typ (density-params at :87-130, labels at
:44-75); keep them in sync by hand, the latex_parity eval is the drift alarm.

Known visual divergences from onyx (deliberate, v1): no contact icons
(separator-joined links instead), round bullet marker instead of the
triangle glyph, no photo (settings.show_photo is coerced off for latex).
"""
from ..schemas import CVData
from .escape import esc

# Copied from templates/typst/common.typ density-params. pt sizes; margins cm.
_DENSITIES = {
    "normal": {
        "base": 10.0, "small": 8.9, "name": 23.5, "headline": 11.4, "h": 9.8,
        "leading": 0.65, "sect_above": 13.0, "sect_below": 6.5,
        "entry_gap": 9.0, "bullet_gap": 4.6, "margin_y": 1.1, "margin_x": 1.15,
    },
    "tight": {
        "base": 9.4, "small": 8.4, "name": 21.5, "headline": 10.6, "h": 9.2,
        "leading": 0.58, "sect_above": 10.0, "sect_below": 5.0,
        "entry_gap": 6.5, "bullet_gap": 3.2, "margin_y": 0.95, "margin_x": 1.05,
    },
    "xtight": {
        "base": 8.9, "small": 8.0, "name": 20.0, "headline": 10.0, "h": 8.7,
        "leading": 0.52, "sect_above": 7.5, "sect_below": 4.0,
        "entry_gap": 4.6, "bullet_gap": 2.2, "margin_y": 0.85, "margin_x": 0.95,
    },
}

# Copied from templates/typst/common.typ labels.
_LABELS = {
    "en": {"summary": "Profile", "experience": "Experience", "education": "Education",
           "skills": "Skills", "projects": "Projects", "languages": "Languages",
           "interests": "Interests", "certifications": "Certifications"},
    "fr": {"summary": "Profil", "experience": "Expérience professionnelle",
           "education": "Formation", "skills": "Compétences", "projects": "Projets",
           "languages": "Langues", "interests": "Centres d'intérêt",
           "certifications": "Certifications"},
    "de": {"summary": "Profil", "experience": "Berufserfahrung", "education": "Ausbildung",
           "skills": "Kenntnisse", "projects": "Projekte", "languages": "Sprachen",
           "interests": "Interessen", "certifications": "Zertifikate"},
}

_FALLBACK_ACCENT = "C2551B"

# Token-substituted preamble: LaTeX braces stay literal (no f-string braces).
_PREAMBLE = r"""\documentclass{article}
\usepackage[a4paper,left=@MX@cm,right=@MX@cm,top=@MY@cm,bottom=@MY@cm]{geometry}
\usepackage{fontspec}
\usepackage{xcolor}
\usepackage[hidelinks]{hyperref}
\setmainfont{IBM Plex Sans}
\newfontfamily\cvmono{IBM Plex Mono}
\definecolor{cvink}{HTML}{16181D}
\definecolor{cvmuted}{HTML}{5C6470}
\definecolor{cvfaint}{HTML}{9AA1AB}
\definecolor{cvaccent}{HTML}{@ACCENT@}
\colorlet{cvaccentlight}{cvaccent!55!white}
\colorlet{cvaccentdark}{cvaccent!96!black}
\colorlet{cvinklight}{cvink!92!white}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\raggedright
\hyphenpenalty=10000
\exhyphenpenalty=10000
\newcommand{\szbase}{\fontsize{@BASE@pt}{@BASELS@pt}\selectfont}
\newcommand{\szsmall}{\fontsize{@SMALL@pt}{@SMALLLS@pt}\selectfont}
\newcommand{\szmark}{\fontsize{@MARK@pt}{@MARK@pt}\selectfont}
\newcommand{\szname}{\fontsize{@NAME@pt}{@NAMELS@pt}\selectfont}
\newcommand{\szheadline}{\fontsize{@HEADLINE@pt}{@HEADLINELS@pt}\selectfont}
\newcommand{\szh}{\fontsize{@H@pt}{@H@pt}\selectfont}
\newcommand{\cvsection}[1]{\par\vspace{@SECTABOVE@pt}\noindent
{\szh\bfseries\color{cvink}\addfontfeatures{LetterSpace=10}\MakeUppercase{#1}}\hspace{9pt}{\color{cvaccentlight}\leaders\hrule height 3.2pt depth -2.5pt\hfill\kern0pt}\par
\vspace{@SECTBELOW@pt}}
\newcommand{\cventry}[4]{\par\vspace{@ENTRYSEP@pt}\noindent
{\szbase\bfseries\color{cvink}#1}\hfill{\szsmall\color{cvmuted}#3}\par
\vspace{2.4pt}\noindent{\szsmall\itshape\color{cvmuted}#2}\hfill{\szsmall\upshape\color{cvfaint}#4}\par}
\newcommand{\cventryfirst}[4]{\par\noindent
{\szbase\bfseries\color{cvink}#1}\hfill{\szsmall\color{cvmuted}#3}\par
\vspace{2.4pt}\noindent{\szsmall\itshape\color{cvmuted}#2}\hfill{\szsmall\upshape\color{cvfaint}#4}\par}
\newcommand{\cvbullet}[1]{\par\vspace{@BULLETGAP@pt}\noindent\hangindent=11pt\hangafter=1
{\color{cvmuted}\szmark\raisebox{0.06em}{$\bullet$}}\hspace{4pt}{\szbase\color{cvinklight}#1}\par}
\newcommand{\cvsep}{{\szsmall\color{cvfaint}\enspace·\enspace}}
"""


def _n(v: float) -> str:
    return f"{round(v, 2):g}"


def _params(settings: dict) -> dict:
    density = settings.get("density", "normal")
    p = dict(_DENSITIES.get(density, _DENSITIES["normal"]))
    try:
        scale = float(settings.get("font_scale") or 1.0)
    except (TypeError, ValueError):
        scale = 1.0
    scale = min(max(scale, 0.8), 1.5)
    gap_scale = max(scale, 1.0)
    for key in ("base", "small", "name", "headline", "h"):
        p[key] = p[key] * scale
    for key in ("sect_above", "sect_below", "entry_gap", "bullet_gap"):
        p[key] = p[key] * gap_scale
    return p


def _accent_hex(settings: dict) -> str:
    raw = str(settings.get("accent") or "").lstrip("#").upper()
    import re as _re

    return raw if _re.fullmatch(r"[0-9A-F]{6}", raw) else _FALLBACK_ACCENT


def _labels(settings: dict) -> dict:
    return _LABELS.get(settings.get("lang", "en"), _LABELS["en"])


def _display_url(v: str) -> str:
    return v.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")


def _href(v: str) -> str:
    return v if v.startswith(("http://", "https://")) else "https://" + v


def _url_arg(v: str) -> str:
    # hyperref's \href url argument: % and # break URLs even inside braces.
    return v.replace("%", "\\%").replace("#", "\\#")


def _date_range(start: str, end: str) -> str:
    if start and end:
        return f"{start} – {end}"
    return start or end


def _contact_line(cv: CVData) -> str:
    c = cv.contacts
    parts: list[str] = []
    if c.location.strip():
        parts.append(esc(c.location))
    if c.phone.strip():
        parts.append(esc(c.phone))
    if c.email.strip():
        parts.append(rf"\href{{mailto:{_url_arg(c.email)}}}{{{esc(c.email)}}}")
    for v in (c.linkedin, c.github, c.website):
        if v.strip():
            parts.append(rf"\href{{{_url_arg(_href(v))}}}{{{esc(_display_url(v))}}}")
    return r"\cvsep{}".join(parts)


def render_tex(data: dict, settings: dict) -> str:
    cv = CVData.model_validate(data or {})
    p = _params(settings or {})
    labels = _labels(settings or {})

    tokens = {
        "@MX@": _n(p["margin_x"]), "@MY@": _n(p["margin_y"]),
        "@ACCENT@": _accent_hex(settings or {}),
        "@BASE@": _n(p["base"]), "@BASELS@": _n(p["base"] * (1 + p["leading"])),
        "@SMALL@": _n(p["small"]), "@SMALLLS@": _n(p["small"] * (1 + p["leading"])),
        "@MARK@": _n(p["small"] * 0.9),
        "@NAME@": _n(p["name"]), "@NAMELS@": _n(p["name"] * 1.05),
        "@HEADLINE@": _n(p["headline"]), "@HEADLINELS@": _n(p["headline"] * 1.15),
        "@H@": _n(p["h"]),
        "@SECTABOVE@": _n(p["sect_above"]), "@SECTBELOW@": _n(p["sect_below"]),
        "@ENTRYSEP@": _n(p["entry_gap"] + 2.0), "@BULLETGAP@": _n(p["bullet_gap"]),
    }
    preamble = _PREAMBLE
    for k, v in tokens.items():
        preamble = preamble.replace(k, v)

    out: list[str] = [preamble, r"\begin{document}"]

    # ---- Header ----
    out.append(rf"{{\szname\bfseries\color{{cvink}}{esc(cv.full_name)}}}\par")
    if cv.headline.strip():
        out.append(r"\vspace{3.2pt}")
        out.append(rf"{{\szheadline\color{{cvaccentdark}}{esc(cv.headline)}}}\par")
    contact = _contact_line(cv)
    if contact:
        out.append(r"\vspace{5.5pt}")
        out.append(rf"{{\szsmall\color{{cvmuted}}{contact}}}\par")
    out.append(r"\vspace{4pt}{\color{cvaccent}\rule{\linewidth}{1.1pt}}\par")

    # ---- Summary ----
    if cv.summary.strip():
        out.append(rf"\cvsection{{{esc(labels['summary'])}}}")
        out.append(rf"{{\szbase\color{{cvinklight}}{esc(cv.summary)}}}\par")

    # ---- Experience ----
    if cv.experience:
        out.append(rf"\cvsection{{{esc(labels['experience'])}}}")
        for i, job in enumerate(cv.experience):
            macro = r"\cventryfirst" if i == 0 else r"\cventry"
            out.append(
                rf"{macro}{{{esc(job.title)}}}{{{esc(job.company)}}}"
                rf"{{{esc(_date_range(job.start, job.end))}}}{{{esc(job.location)}}}"
            )
            for b in job.bullets:
                out.append(rf"\cvbullet{{{esc(b)}}}")

    # ---- Projects ----
    if cv.projects:
        out.append(rf"\cvsection{{{esc(labels['projects'])}}}")
        for i, proj in enumerate(cv.projects):
            if i > 0:
                out.append(rf"\vspace{{{tokens['@ENTRYSEP@']}pt}}")
            out.append(
                rf"\noindent{{\szbase\bfseries\color{{cvink}}{esc(proj.name)}}}\hfill"
                rf"{{\szsmall\cvmono\color{{cvfaint}}{esc(proj.tech)}}}\par"
            )
            if proj.description.strip():
                out.append(rf"\cvbullet{{{esc(proj.description)}}}")

    # ---- Education ----
    if cv.education:
        out.append(rf"\cvsection{{{esc(labels['education'])}}}")
        for i, ed in enumerate(cv.education):
            macro = r"\cventryfirst" if i == 0 else r"\cventry"
            out.append(
                rf"{macro}{{{esc(ed.degree)}}}{{{esc(ed.school)}}}"
                rf"{{{esc(_date_range(ed.start, ed.end))}}}{{{esc(ed.location)}}}"
            )
            if ed.details:
                out.append(r"\vspace{1.8pt}")
                joined = esc("  ·  ").join(esc(d) for d in ed.details)
                out.append(rf"\noindent{{\szsmall\color{{cvmuted}}{joined}}}\par")

    # ---- Skills ----
    if cv.skills:
        out.append(rf"\cvsection{{{esc(labels['skills'])}}}")
        for i, group in enumerate(cv.skills):
            if i > 0:
                out.append(r"\vspace{2.6pt}")
            items = esc("  ·  ").join(esc(it) for it in group.items)
            out.append(
                rf"\noindent{{\szsmall\bfseries\color{{cvink}}{esc(group.category)}}}"
                rf"\hspace{{8pt}}{{\szsmall\color{{cvmuted}}{items}}}\par"
            )

    # ---- Certifications ----
    if cv.certifications:
        out.append(rf"\cvsection{{{esc(labels['certifications'])}}}")
        for cert in cv.certifications:
            bits = [b for b in (cert.name, cert.issuer, cert.year) if b.strip()]
            joined = esc("  ·  ").join(esc(b) for b in bits)
            out.append(rf"\noindent{{\szsmall\color{{cvinklight}}{joined}}}\par")

    # ---- Languages + interests footer ----
    if cv.languages or cv.interests:
        key = "languages" if cv.languages else "interests"
        out.append(rf"\cvsection{{{esc(labels[key])}}}")
        if cv.languages:
            parts = []
            for lang in cv.languages:
                name = rf"{{\szsmall\bfseries\color{{cvink}}{esc(lang.name)}}}"
                if lang.level.strip():
                    name += rf" {{\szsmall\color{{cvfaint}}({esc(lang.level)})}}"
                parts.append(name)
            out.append(r"\noindent" + r"{\szsmall\color{cvfaint}\enspace·\enspace}".join(parts) + r"\par")
        if cv.interests:
            if cv.languages:
                out.append(r"\vspace{2.6pt}")
            joined = esc("  ·  ").join(esc(it) for it in cv.interests)
            out.append(rf"\noindent{{\szsmall\color{{cvmuted}}{joined}}}\par")

    out.append(r"\end{document}")
    return "\n".join(out) + "\n"
