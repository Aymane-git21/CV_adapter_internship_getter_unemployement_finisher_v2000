"""Distilled Typst grounding for source-mode AI edits.

Typst (2023+) is barely represented in LLM training data next to LaTeX, so
models drift into LaTeX habits or invent syntax when editing raw source.
This primer is the curated context injected into every source edit/repair
prompt: small on purpose, tuned to the exact source shape this app
generates. Distilled from typst.app/docs (v0.14), the official
guide-for-latex-users, and community material indexed at
github.com/qjcg/awesome-typst (notably the Typst Examples Book).
"""

TYPST_PRIMER = """TYPST REFERENCE (typst.app markup language, v0.14; this is NOT LaTeX)

DOCUMENT ANATOMY of the source you are editing:
  #import "/typst/cv_onyx.typ": render    <- template; path must stay under /typst/
  #let settings = ( ... )                 <- rendering knobs, a dict
  #let data = ( ... )                     <- ALL document content, a dict
  #let photo = none
  #render(data, settings, photo: photo)   <- must remain the last line
Most requests are satisfied by editing values inside `data` or `settings`.
Prefer that over adding markup or styling code.

SETTINGS KNOBS (use these before writing any styling code):
  template: "onyx" | "classic" | "compact"   accent: "#RRGGBB" hex string
  density: "normal" | "tight" | "xtight"     font_scale: 1.0 (float, whole doc)
  show_photo: true | false                   lang: "en" | "fr" | "de"
Changing template means also changing the import path to /typst/cv_<name>.typ.

DATA KEYS the templates read (never rename them, never invent new ones):
  full_name, headline, summary,
  contacts: (email, phone, location, linkedin, github, website),
  experience: array of (title, company, location, start, end, bullets),
  education: array of (degree, school, location, start, end, details),
  skills: array of (category, items), projects: array of (name, tech, description),
  languages: array of (name, level), interests, certifications: (name, issuer, year).

LITERAL SYNTAX inside #let (code mode):
  dict:  (key: "value", n: 3)      empty dict is (:)
  array: ("a", "b")                single-element array MUST be ("a",) with comma
  trailing commas are always allowed; true/false/none are lowercase bare words
  strings are double-quoted; escape only \\" and \\\\; \\n is a newline

TYPST IS NOT LATEX — the mistakes that break compilation:
  \\textbf{x}, \\section{}, \\item   -> invalid. No backslash commands exist.
  \\begin{...} / \\end{...}          -> invalid. No environments exist.
  \\\\ line break                    -> invalid. Use \\n inside a string.
  % comment                          -> % is a literal percent. Comments: // and /* */
  {} for arguments                   -> functions use parens with named args,
                                        content in brackets: #text(size: 11pt)[Hi]

GLOBAL STYLING, only when no settings knob covers it: insert #set / #show lines
AFTER the #import line and BEFORE #render, e.g.
  #set text(size: 11pt)
  #show heading: set text(fill: rgb("#0F62FE"))
Lengths: 10pt, 1.2em, 2cm. Colors: rgb("#RRGGBB").

MARKUP MODE (only inside [...] content blocks, NOT inside "strings"):
  *bold*  _italic_  special chars # $ * _ ` @ < > escape with backslash: C\\#
  TRAP: after #variable an underscore is EATEN INTO the identifier, so
  _#company_ fails with "unclosed delimiter" (parses as #company_ ).
  Terminate interpolation with ; ( _#company;_ ) or use #emph[#company].
"""
