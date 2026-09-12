"""Deterministic ATS keyword-coverage scoring.

The legacy app asked the LLM to grade its own homework (the "after" prompt
literally contained the example answer 95). Here the score is computed:
keywords come from one analysis call, then coverage is string matching —
the same keyword set scores the master CV (before) and the tailored CV
(after), so the delta is real.
"""
import re
import unicodedata

from .doctext import cv_text
from .schemas import CVData, Keyword, SkillGroup

# Overboard's backstop group, created only when the CV has no skills at all.
_COVERAGE_GROUP = {"en": "Key skills", "fr": "Compétences clés", "de": "Kernkompetenzen"}


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


def matchable(term: str) -> bool:
    """Whether any text can ever match `term`: normalization has to leave
    something, and a term with no Latin letter or digit normalizes to nothing."""
    return bool(normalize(term).strip())


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


def cover_all_keywords(keywords: list[Keyword], cv: CVData, language: str = "en") -> CVData:
    """Overboard mode's guarantee of a 100% match. The model is told to place
    every keyword; whatever it still missed is appended to the first skills
    group (or a new one), each as its own item. score() is certain to find an
    item added this way: it runs the same normalize() over the same cv_text.
    An unmatchable term is replaced by its first matchable alias; with none it
    stays missing, since no text could ever match it. Returns a new CVData and
    never mutates the input."""
    haystack = normalize(cv_text(cv.model_dump()))
    additions: list[str] = []
    for kw in keywords:
        spellings = [kw.term, *kw.aliases]
        if any(_present(s, haystack) for s in spellings):
            continue
        chosen = next((s.strip() for s in spellings if matchable(s)), None)
        if chosen is None:
            continue
        additions.append(chosen)
        # Later keywords that normalize the same way ("CI/CD", "CI CD") are
        # then already present and not listed twice.
        haystack += normalize(chosen)
    if not additions:
        return cv
    out = cv.model_copy(deep=True)
    if out.skills:
        out.skills[0].items = [*out.skills[0].items, *additions]
    else:
        label = _COVERAGE_GROUP.get(language, _COVERAGE_GROUP["en"])
        out.skills = [SkillGroup(category=label, items=additions)]
    return out
