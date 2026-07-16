"""Deterministic scoring for AI-writing evals. No LLM calls in here: every
metric is same-input-same-output code so eval thresholds are reproducible."""
import re

_WORD = re.compile(r"[a-zà-öø-ÿ0-9+#]+")
_DIGITS = re.compile(r"\d+")


def tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def bullet_novelty(bullet: str, master_bullets: list[str]) -> float:
    """1 minus the max token overlap with any master bullet.
    0.0 = verbatim copy of a master bullet, 1.0 = entirely fresh wording."""
    if not master_bullets:
        return 1.0
    return 1.0 - max(jaccard(bullet, m) for m in master_bullets)


def numbers_in(text: str) -> set[str]:
    """Every digit run, zero-stripped: '1,200' -> {'1','200'}, '007' -> {'7'}.
    Comparing digit runs instead of parsed values keeps '1,200' vs '1 200'
    locale reformatting from reading as a new number. All-zero runs are
    dropped: expanding '40k' to '40,000' adds a '000' run but no new
    significant digits, so it is reformatting, not fabrication."""
    out = set()
    for d in _DIGITS.findall(text):
        d = d.lstrip("0")
        if d:
            out.add(d)
    return out


def fabricated_numbers(tailored_text: str, sources: list[str]) -> list[str]:
    """Digit runs in the tailored text that appear in no source text. A
    non-empty result means the model invented a metric: hard eval failure."""
    allowed: set[str] = set()
    for src in sources:
        allowed |= numbers_in(src)
    return sorted(numbers_in(tailored_text) - allowed)
