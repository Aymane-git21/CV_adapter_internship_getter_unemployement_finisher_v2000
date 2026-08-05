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


# ---- one-page budget ------------------------------------------------------

def content_lines(cv: dict) -> int:
    """Experience bullets plus project descriptions: the two things the tailor
    prompt budgets (rule 2) and what the one-page fit actually spends. Measured
    against the real onyx template, 10 of these fill an A4 page at `tight` and
    15 is the ceiling at `xtight`, past which the fit loop runs out of levers."""
    bullets = sum(len(j.get("bullets") or []) for j in cv.get("experience") or [])
    projects = sum(
        1 for p in cv.get("projects") or [] if (p.get("description") or "").strip()
    )
    return bullets + projects


def em_dash_fields(value, master_text: str = "", path: str = "") -> list[str]:
    """Dotted paths of fields carrying an em dash the MODEL introduced, as
    paths rather than a bare boolean so a failure says where to look. A value
    appearing verbatim in the master CV is inherited, not written: role titles
    are locked facts, so "Research Intern — Computer Vision" has to survive
    even though the prompt bans em dashes in wording the model authors."""
    out: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            out += em_dash_fields(v, master_text, f"{path}.{k}" if path else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out += em_dash_fields(v, master_text, f"{path}[{i}]")
    elif isinstance(value, str) and "—" in value and value not in master_text:
        out.append(path or "<root>")
    return out


def content_line_budget(cv: dict) -> int:
    """How many content lines THIS CV's shape can carry, mirroring the tailor
    prompt's rule 2. A flat number would be wrong: compiling the real template
    gives 15 content lines for a lean CV (3 roles, 2 degrees, 3 skill groups)
    but only 8 for one carrying 4 roles, 3 degrees and 4 skill groups, because
    that furniture spends the same page. 12 baseline, minus one per extra."""
    budget = 12
    budget -= max(0, len(cv.get("experience") or []) - 3)
    budget -= max(0, len(cv.get("education") or []) - 2)
    budget -= max(0, len(cv.get("skills") or []) - 3)
    return max(6, budget)


# ---- wording quality ------------------------------------------------------

# Adjectives and verbs that survive deletion without costing information. The
# tailor prompt bans introducing them (rule 7); a word the master CV already
# used for that fact is the candidate's own voice and does not count.
FILLER_WORDS = frozenset({
    "robust", "critical", "strict", "advanced", "comprehensive", "cutting-edge",
    "state-of-the-art", "seamless", "high-integrity", "high-availability",
    "production-grade", "leverage", "spearhead", "passionate", "dynamic",
    "innovative", "synergy", "adaptable",
})

def _stem_pattern(word: str) -> str:
    """A filler word plus its common inflections. Words ending in 'e' drop it
    before a suffix, so leverage has to also catch leveraging."""
    if word.endswith("e"):
        return r"\b" + re.escape(word[:-1]) + r"(?:e|es|ed|ing|ely)\b"
    return r"\b" + re.escape(word) + r"(?:ly|ness|ed|es|s|ing)?\b"


_FILLER_PATTERNS = {w: re.compile(_stem_pattern(w), re.I) for w in FILLER_WORDS}

# Closing constructions of the "verb + what + to <purpose>" template. One is
# fine; every bullet ending this way is the monotony that reads machine-written.
#
# "to" is matched only before an outcome verb, never bare: a bare `to\s+\w+`
# also catches the preposition in "routing to fine-tuned models", "migrated to
# Kubernetes" and "from days to hours", which inflated the score by ~20 points
# and made the metric fail runs that were actually fine.
_PURPOSE_MARK = re.compile(
    r"\b(?:ensuring|enabling|allowing|guaranteeing|streamlining|supporting"
    r"|to\s+(?:reduce|improve|ensure|enable|support|guarantee|streamline"
    r"|accelerate|create|maximi[sz]e|minimi[sz]e|drive|deliver|eliminate"
    r"|boost|increase|decrease|optimi[sz]e|standardi[sz]e|unify|centralize"
    r"|allow|provide|achieve|strengthen|simplify))\b",
    re.I,
)
# How far into a bullet a marker has to sit to count as a CLOSING clause:
# "Migrated to Kubernetes" opens with one, "pipelines to guarantee X" closes
# with one, and the boundary between them sits around a third of the way in.
_PURPOSE_MIN_POS = 0.35

_PAREN = re.compile(r"\s*\([^)]*\)")
_SKILL_NOISE = frozenset({"and", "the", "for", "with", "core", "tools", "based"})


def _filler_hits(text: str) -> set[str]:
    return {w for w, rx in _FILLER_PATTERNS.items() if rx.search(text)}


def filler_words(text: str, master_text: str = "") -> list[str]:
    """Banned filler introduced by the model, i.e. present in the tailored text
    and absent from the master CV."""
    return sorted(_filler_hits(text) - _filler_hits(master_text))


def purpose_clause_fraction(bullets: list[str]) -> float:
    """Fraction of bullets closing on a purpose clause. Near 1.0 means every
    bullet was poured into the same mould, which rule 6 forbids."""
    if not bullets:
        return 0.0
    hits = 0
    for b in bullets:
        b = b.strip()
        if not b:
            continue
        floor = len(b) * _PURPOSE_MIN_POS
        if any(m.start() >= floor for m in _PURPOSE_MARK.finditer(b)):
            hits += 1
    return hits / len(bullets)


def repeated_openers(bullets: list[str]) -> list[str]:
    """Opening words shared by two or more of the given bullets. Rule 6 forbids
    two bullets in one entry starting with the same verb."""
    first = [b.strip().split()[0].lower() for b in bullets if b.strip()]
    return sorted({w for w in first if first.count(w) > 1})


def unevidenced_skills(cv: dict, master_text: str) -> list[str]:
    """Skill items backed by nothing: absent from the tailored CV's own prose
    AND from the master CV. Matching is per token, not by substring, because
    rewording a skill is allowed and only invention is not: a master listing
    "monitoring & drift" legitimately becomes "Model Monitoring" and
    "Drift Detection", which a substring check would flag. Parentheticals are
    stripped so "Kubernetes (GKE)" is evidenced by "kubernetes"."""
    prose = [cv.get("summary") or "", cv.get("headline") or ""]
    for j in cv.get("experience") or []:
        prose += [j.get("title") or "", j.get("company") or ""]
        prose += list(j.get("bullets") or [])
    for p in cv.get("projects") or []:
        prose += [p.get("name") or "", p.get("tech") or "", p.get("description") or ""]
    for e in cv.get("education") or []:
        prose += [e.get("degree") or "", e.get("school") or ""]
        prose += list(e.get("details") or [])
    for c in cv.get("certifications") or []:
        prose += [c.get("name") or "", c.get("issuer") or ""]
    haystack = (" ".join(prose) + " " + master_text).lower()

    hay = tokens(haystack)
    out: set[str] = set()
    for group in cv.get("skills") or []:
        for item in group.get("items") or []:
            probe = tokens(_PAREN.sub("", item))
            # Ignore connective noise, but keep short technology names (Go, C#,
            # AWS) when that is all the item is made of.
            significant = {t for t in probe if len(t) >= 4 and t not in _SKILL_NOISE}
            significant = significant or probe
            if significant and not significant <= hay:
                out.add(item)
    return sorted(out)
