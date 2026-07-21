"""Prompts for the docgen comparison bench.

Fairness contract:
- Every pipeline gets the same design brief and the same CV JSON.
- Each format gets a grounding block sized to what a production prompt for
  that format would realistically carry. Typst's block is the largest
  because Typst is sparse in training data — that asymmetry is part of what
  the bench measures (the primer is the mitigation the app already ships).
- Every pipeline gets the same repair budget: one round, with the real
  compiler diagnostics, mirroring backend/app/ai/prompts.py:repair_source_prompt.
"""

DESIGN_BRIEF = """DESIGN BRIEF (hard rules):
1. Exactly ONE A4 page, compact but readable: body ~9.5-10.5pt, margins 1.2-1.5cm.
2. Structure: header (name, headline, one contact line), then sections
   Summary, Experience, Education, Skills, Projects, Languages & Certifications.
3. Render ALL content from the JSON faithfully: every experience entry with all
   its bullets, every education entry, all skill categories, all projects,
   languages, certifications, interests. Never invent, drop, or reword facts.
4. Section headings in the accent color #0F62FE, small caps or uppercase, with
   a thin horizontal rule under each.
5. Entry rows: role and organization on the left, location and dates dimmed on
   the right (or after the title if the format cannot right-align).
6. No photo, no icons, no tables of contents, no page numbers, no external
   files, images, or web assets. The document must be fully self-contained."""

TYPST_NOTES = """TYPST REFERENCE (typst.app markup, v0.14 — this is NOT LaTeX):
- No backslash commands and no environments: \\textbf{}, \\begin{}, \\item are
  all invalid. Functions are called like #text(size: 10pt)[content].
- Markup mode: *bold* _italic_; bullet lines start with "- "; headings are
  "= Title" / "== Section". Escape these in plain text: # $ * _ @ ` (e.g. C\\#,
  name\\@host). % is a literal percent; comments are // and /* */.
- Code mode after #: #set page(paper: "a4", margin: (x: 1.4cm, y: 1.2cm)),
  #set text(size: 10pt), #set par(leading: 0.6em).
- Styling: #show heading.where(level: 2): it => block[...] customizes section
  headings; #line(length: 100%, stroke: 0.6pt + rgb("#0F62FE")) draws rules;
  #grid(columns: (1fr, auto), left, right) makes two-column rows;
  #v(4pt) inserts vertical space.
- Colors: rgb("#RRGGBB"). Lengths: pt, em, cm. Fonts: #set text(font: "...").
- Literals: dict (key: "v", n: 3); array ("a", "b"); a SINGLE-element array
  needs a trailing comma ("x",); true/false/none are lowercase bare words;
  strings are double-quoted.
- TRAP: after #variable an underscore is EATEN INTO the identifier, so
  _#company_ fails with "unclosed delimiter". Terminate interpolation with ;
  ( _#company;_ ) or use #emph[#company]."""

LATEX_NOTES = """LATEX RULES for this build (compiled by Tectonic, XeTeX engine):
- \\documentclass{article}. Allowed packages (all available): geometry,
  fontspec, xcolor, enumitem, titlesec, hyperref, parskip, tabularx, ragged2e,
  setspace. Do NOT use: moderncv, altacv, fontawesome, tikz, images,
  shell-escape, or any package beyond the list.
- Load fontspec (the text contains accented characters like é).
- \\pagestyle{empty}. Escape & % # _ in text as \\& \\% \\# \\_. Write < as
  \\textless{} in text mode.
- One self-contained .tex file that compiles standalone."""

QMD_NOTES = """QUARTO RULES (rendered with `quarto render file.qmd --to typst`):
- One .qmd file: YAML front matter, then a markdown body.
- YAML skeleton (do NOT set title/author keys — put the name in the body):
---
format:
  typst:
    papersize: a4
    margin:
      x: 1.4cm
      y: 1.2cm
    fontsize: 10pt
---
- Body is plain markdown: "# Name", "## Section" headings, "-" bullets,
  **bold**, *italic*. Quarto/Pandoc handles all character escaping.
- For styling beyond markdown (accent colors, heading rules, spacing), embed
  raw Typst blocks; they pass straight through to the Typst compiler:
```{=typst}
#show heading.where(level: 2): set text(fill: rgb("#0F62FE"))
```
"""


def author_prompt(fmt_label: str, notes: str, cv_json: str) -> str:
    return f"""You are an elite CV typesetter. Write a complete {fmt_label} document that
renders the candidate CV below as a polished, professional, ATS-friendly CV.

{DESIGN_BRIEF}

{notes}

CANDIDATE CV (JSON — the single source of truth):
{cv_json}

Return ONLY the complete raw {fmt_label} source. No code fences, no commentary."""


def edit_prompt(fmt_label: str, notes: str, source: str, instruction: str) -> str:
    return f"""You are editing a {fmt_label} document. Apply the instruction and return the
COMPLETE updated source file, nothing else.

{notes}

RULES:
- Change only what the instruction requires; keep everything else intact.
- The result must still compile and still fit one A4 page.

INSTRUCTION: {instruction}

CURRENT SOURCE:
```
{source}
```
Return only the raw updated source (no fences)."""


def repair_prompt(fmt_label: str, notes: str, source: str, diagnostics: str) -> str:
    return f"""The {fmt_label} source below fails to compile. Fix it with the SMALLEST
possible change and return the COMPLETE corrected source, nothing else.
Do not rewrite or restructure anything the errors do not require.

{notes}

COMPILER ERRORS:
{diagnostics}

SOURCE:
```
{source}
```
Return only the raw corrected source (no fences)."""
