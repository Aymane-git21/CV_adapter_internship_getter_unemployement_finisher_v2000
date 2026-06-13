"""Deterministic ATS keyword-coverage scoring.

The legacy app asked the LLM to grade its own homework (the "after" prompt
literally contained the example answer 95). Here the score is computed:
keywords come from one analysis call, then coverage is string matching —
the same keyword set scores the master CV (before) and the tailored CV
(after), so the delta is real.
"""
import re
import unicodedata

from .schemas import Keyword


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return f" {text} "


def _present(term: str, haystack: str) -> bool:
    t = normalize(term).strip()
    if not t:
        return False
    # Word-ish boundary match; multi-word terms tolerate flexible whitespace.
    pattern = r"(?<![a-z0-9])" + r"\s+".join(re.escape(w) for w in t.split()) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def score(keywords: list[Keyword], text: str) -> dict:
    haystack = normalize(text)
    matched: list[str] = []
    missing: list[str] = []
    got, total = 0, 0
    for kw in keywords:
        weight = max(1, min(3, kw.weight))
        total += weight
        hit = _present(kw.term, haystack) or any(_present(a, haystack) for a in kw.aliases)
        if hit:
            got += weight
            matched.append(kw.term)
        else:
            missing.append(kw.term)
    pct = round(100 * got / total) if total else 0
    return {"score": pct, "matched": matched, "missing": missing}
