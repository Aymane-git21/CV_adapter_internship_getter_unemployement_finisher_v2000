"""Deterministic PDF checks: text extraction, content fidelity, ordering.

Fidelity = fraction of required CV tokens (names, employers, schools,
projects, certifications, languages) present in the extracted PDF text.
This catches the silent failure mode of AI-authored markup: the document
compiles but content was dropped or mangled.
"""
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFKC (folds ligatures like ﬁ), strip soft hyphens, lowercase, collapse ws."""
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("­", "")
    return _WS.sub(" ", t).lower().strip()


def pdf_text_pages(path: Path) -> tuple[str, int]:
    reader = PdfReader(str(path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return text, len(reader.pages)


def required_tokens(cv: dict) -> list[str]:
    tokens = [cv["full_name"], cv["contacts"]["email"]]
    tokens += [e["company"] for e in cv.get("experience", [])]
    tokens += [e["school"] for e in cv.get("education", [])]
    tokens += [p["name"] for p in cv.get("projects", [])]
    tokens += [c["name"] for c in cv.get("certifications", [])]
    tokens += [lang["name"] for lang in cv.get("languages", [])]
    return [t for t in tokens if t]


def score(text: str, tokens: list[str]) -> tuple[float, list[str]]:
    """(fraction of tokens present, missing tokens). Text is raw; both sides normalized."""
    haystack = normalize(text)
    missing = [t for t in tokens if normalize(t) not in haystack]
    return (len(tokens) - len(missing)) / len(tokens) if tokens else 1.0, missing


def appears_before(text: str, first: str, second: str) -> bool:
    """True if `first` occurs before `second` in the normalized text (both present)."""
    haystack = normalize(text)
    i, j = haystack.find(normalize(first)), haystack.find(normalize(second))
    return i != -1 and j != -1 and i < j
