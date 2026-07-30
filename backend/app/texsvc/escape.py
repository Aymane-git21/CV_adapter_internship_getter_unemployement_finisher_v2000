"""LaTeX escaping. Single simultaneous-pass regex: sequential str.replace
would double-escape the backslash expansion. Mirrors the typst_literal
contract (renderer.typst_literal): user strings are data, never markup."""
import re
import unicodedata

_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_RE = re.compile("|".join(re.escape(k) for k in _SPECIALS))


def esc(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace("\u2028", "\n").replace("\u2029", "\n")
    s = "".join(ch for ch in s if ch == "\n" or ord(ch) >= 32)
    return _RE.sub(lambda m: _SPECIALS[m.group(0)], s)
