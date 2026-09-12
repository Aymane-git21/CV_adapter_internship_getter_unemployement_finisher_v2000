"""Document text for ATS keyword scoring, whichever editor changed it.

The structured form and the assistant edit `data`; the source editor edits the
Typst or LaTeX source directly. Every path reduces to the text the document
shows. A data-mode document and the Typst source rendered from it yield the
SAME string: typst_literal writes each string leaf of `data` as exactly one
string literal inside `#let data = (...)`, in the same depth-first order, so
switching editors never moves the score by itself; only content does. That
invariant is pinned in backend/tests/test_doctext.py.
"""
import re

_DATA_LET = re.compile(r"^[ \t]*#let[ \t]+data[ \t]*=[ \t]*", re.M)
_SETTINGS_LET = re.compile(r"^[ \t]*#let[ \t]+settings[ \t]*=[ \t]*", re.M)
_IMPORT_LINE = re.compile(r"^[ \t]*#import[^\n]*", re.M)
_TYPST_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t"}

_TEX_BODY = re.compile(r"\\begin\{document\}(.*?)(?:\\end\{document\}|\Z)", re.S)
_TEX_COMMENT = re.compile(r"(?<!\\)%[^\n]*")
# The escapes texsvc.escape writes for special characters.
_TEX_ESCAPED = (
    ("\\&", "&"), ("\\%", "%"), ("\\#", "#"), ("\\_", "_"), ("\\$", "$"),
    ("\\{", "{"), ("\\}", "}"),
)
_TEX_SYMBOL_WORDS = re.compile(r"\\text(?:backslash|asciitilde|asciicircum)\{\}")
_TEX_CONTROL = re.compile(r"\\[a-zA-Z@]+\*?|\\.", re.S)
_TEX_GROUPING = re.compile(r"[{}\[\]]")


def _join(strings) -> str:
    # Carriage returns are dropped exactly as the Typst literal writer drops
    # them, and empty strings leave no trace in either representation.
    cleaned = (s.replace("\r", "") for s in strings)
    return "\n".join(s for s in cleaned if s)


def _leaves(value, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _leaves(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _leaves(v, out)


def cv_text(data) -> str:
    """Every string leaf of a document's data, depth-first, one per line."""
    out: list[str] = []
    _leaves(data, out)
    return _join(out)


def _read_string(src: str, i: int) -> tuple[str, int]:
    """Decode the Typst string literal whose opening quote sits at src[i].
    Returns (value, index just past the closing quote)."""
    buf: list[str] = []
    j, n = i + 1, len(src)
    while j < n and src[j] != '"':
        ch = src[j]
        if ch == "\\" and j + 1 < n:
            nxt = src[j + 1]
            if nxt == "u" and src.startswith("{", j + 2):
                close = src.find("}", j + 3)
                if close != -1:
                    try:
                        buf.append(chr(int(src[j + 3:close], 16)))
                        j = close + 1
                        continue
                    except ValueError:
                        pass
            buf.append(_TYPST_ESCAPES.get(nxt, nxt))
            j += 2
            continue
        buf.append(ch)
        j += 1
    return "".join(buf), j + 1


def _scan(src: str, start: int, one_group: bool) -> tuple[list[str], int]:
    """String literals in src from `start`, skipping // and /* */ comments.
    With one_group, stops just past the bracket that closes the first group
    opened (the `(` of `#let data = (`), or at the end of the line when no
    group opens on it (`#let data = none`). Returns (strings, stop index)."""
    strings: list[str] = []
    depth, opened = 0, False
    i, n = start, len(src)
    while i < n:
        ch = src[i]
        if ch == '"':
            value, i = _read_string(src, i)
            strings.append(value)
            continue
        if src.startswith("//", i):
            nl = src.find("\n", i)
            i = n if nl == -1 else nl
            continue
        if src.startswith("/*", i):
            end = src.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if ch in "([{":
            depth += 1
            opened = True
        elif ch in ")]}":
            depth -= 1
            if one_group and opened and depth == 0:
                return strings, i + 1
        elif ch == "\n" and one_group and not opened:
            return strings, i
        i += 1
    return strings, n


def typst_source_text(source: str) -> str:
    """Text of a (possibly hand-edited) Typst document: the string literals of
    its `#let data = (...)` block. When that block is gone (restructured by
    hand), every string literal outside the #import lines and the settings
    dict, which is the closest honest reading of the page."""
    m = _DATA_LET.search(source)
    if m:
        strings, _ = _scan(source, m.end(), one_group=True)
        return _join(strings)
    text = source
    settings = _SETTINGS_LET.search(text)
    if settings:
        _, end = _scan(text, settings.end(), one_group=True)
        text = text[: settings.start()] + text[end:]
    text = _IMPORT_LINE.sub("", text)
    strings, _ = _scan(text, 0, one_group=False)
    return _join(strings)


def tex_source_text(source: str) -> str:
    """Visible text of a (possibly hand-edited) LaTeX document, approximately:
    the document body with comments, control sequences and grouping
    characters removed and the special-character escapes decoded."""
    m = _TEX_BODY.search(source)
    body = m.group(1) if m else source
    body = _TEX_COMMENT.sub("", body)
    body = body.replace("\\\\", "\n")
    for escaped, char in _TEX_ESCAPED:
        body = body.replace(escaped, char)
    body = _TEX_SYMBOL_WORDS.sub(" ", body)
    body = _TEX_CONTROL.sub(" ", body)
    return _TEX_GROUPING.sub(" ", body)
