"""Periodic eval, paid lane (a few flash calls per run).

Measures whether tailor_cv actually REWRITES and boosts the CV instead of
transcribing the master, while inventing zero numbers. Also runs an
intensity matrix (reshape/major/max_ats) and asserts the novelty and
ATS-score orderings between levels. All scoring is deterministic
(backend/evals/metrics.py); only the generation is latent.

Run: python -m backend.evals.eval_tailor_boost [runs]
Exit 0 = pass (or no key configured, printed as SKIPPED), 1 = fail.
"""
import asyncio
import json
import sys
from pathlib import Path

from backend.app import ats
from backend.app.ai import get_provider
from backend.app.config import get_settings
from backend.app.schemas import CVData
from backend.evals import metrics

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

JD = """Machine Learning Engineer at Lumina AI in Paris.
You will design RAG pipelines, deploy models with docker and kubernetes on GCP,
and build evaluation harnesses in python. Experience with pytorch, airflow,
and LLM systems in production is required. Strong MLOps culture. You own your
models end to end: monitoring, drift detection, rollback."""

# Thresholds. Novelty is 1 - max token-jaccard against the master bullets;
# a transcribed CV scores ~0.0-0.1 mean novelty, a properly rewritten one
# lands 0.4+. Copies = bullets with jaccard >= 0.85 against a master bullet.
MIN_MEAN_NOVELTY = 0.35
MAX_COPY_FRACTION = 0.20
MAX_SUMMARY_JACCARD = 0.60
SUMMARY_WORDS = (25, 95)
MIN_KEYWORD_HITS = 5

# The one-page budget is shape-dependent, so it comes from
# metrics.content_line_budget rather than a constant here: a lean CV carries 15
# content lines, one with 4 roles / 3 degrees / 4 skill groups only 8. Past its
# budget the fit loop runs out of levers and the CV really does spill to a
# second page, so the eval fails rather than shipping it.
#
# Some bullets legitimately end on a purpose clause; every one of them doing so
# is the single-template monotony that reads machine-written.
MAX_PURPOSE_FRACTION = 0.60


def _check(name: str, ok: bool, detail: str) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    return ok


async def run_once(provider, master: CVData) -> bool:
    analysis = await provider.analyze(JD, master.plain_text(), "en")
    tailored = await provider.tailor_cv(JD, analysis, master, "en")

    master_bullets = [b for job in master.experience for b in job.bullets]
    tailored_bullets = [b for job in tailored.experience for b in job.bullets]
    assert tailored_bullets, "tailored CV has no bullets"

    novelties = [metrics.bullet_novelty(b, master_bullets) for b in tailored_bullets]
    mean_novelty = sum(novelties) / len(novelties)
    copies = sum(1 for n in novelties if n <= 0.15) / len(novelties)
    summary_overlap = metrics.jaccard(tailored.summary, master.summary)
    summary_len = len(tailored.summary.split())

    tailored_text = json.dumps(tailored.model_dump(), ensure_ascii=False)
    fabricated = metrics.fabricated_numbers(
        tailored_text, [json.dumps(master.model_dump(), ensure_ascii=False), JD]
    )

    kw_terms = [k.term.lower() for k in analysis.keywords][:10]
    low_text = tailored_text.lower()
    kw_hits = sum(1 for t in kw_terms if t in low_text)

    master_text = json.dumps(master.model_dump(), ensure_ascii=False)
    tailored_dump = tailored.model_dump()
    lines = metrics.content_lines(tailored_dump)
    budget_lines = metrics.content_line_budget(tailored_dump)
    filler = metrics.filler_words(tailored_text, master_text)
    purpose = metrics.purpose_clause_fraction(tailored_bullets)
    dup_openers = [
        (job.company, dups)
        for job in tailored.experience
        if (dups := metrics.repeated_openers(job.bullets))
    ]
    unevidenced = metrics.unevidenced_skills(tailored_dump, master_text)

    ok = True
    ok &= _check("mean bullet novelty", mean_novelty >= MIN_MEAN_NOVELTY,
                 f"{mean_novelty:.2f} (min {MIN_MEAN_NOVELTY})")
    ok &= _check("verbatim-copy fraction", copies <= MAX_COPY_FRACTION,
                 f"{copies:.2f} (max {MAX_COPY_FRACTION})")
    ok &= _check("summary rewritten", summary_overlap <= MAX_SUMMARY_JACCARD,
                 f"jaccard {summary_overlap:.2f} (max {MAX_SUMMARY_JACCARD})")
    ok &= _check("summary length", SUMMARY_WORDS[0] <= summary_len <= SUMMARY_WORDS[1],
                 f"{summary_len} words (want {SUMMARY_WORDS[0]}-{SUMMARY_WORDS[1]})")
    ok &= _check("no fabricated numbers", not fabricated, f"{fabricated or 'none'}")
    ok &= _check("keyword coverage", kw_hits >= MIN_KEYWORD_HITS,
                 f"{kw_hits}/10 top terms (min {MIN_KEYWORD_HITS})")
    em_dashes = metrics.em_dash_fields(tailored_dump, master_text)
    ok &= _check("no em dash", not em_dashes, f"{em_dashes or 'clean'}")
    ok &= _check("one-page budget", lines <= budget_lines,
                 f"{lines} content lines, budget {budget_lines} for "
                 f"{len(tailored.experience)} roles / {len(tailored.education)} degrees"
                 f" / {len(tailored.skills)} skill groups")
    ok &= _check("no filler adjectives", not filler, f"{filler or 'clean'}")
    ok &= _check("bullet shape varies", purpose <= MAX_PURPOSE_FRACTION,
                 f"{purpose:.0%} close on a purpose clause "
                 f"(max {MAX_PURPOSE_FRACTION:.0%})")
    ok &= _check("no repeated openers per entry", not dup_openers,
                 f"{dup_openers or 'clean'}")
    ok &= _check("skills are evidenced", not unevidenced, f"{unevidenced or 'clean'}")
    return bool(ok)


async def run_intensity_matrix(provider, master: CVData) -> bool:
    """Generate at three intensity levels and assert the orderings:
    novelty(reshape) < novelty(major) <= novelty(max_ats) and
    ATS after-score(max_ats) >= after-score(major) >= after-score(reshape)."""
    analysis = await provider.analyze(JD, master.plain_text(), "en")
    master_bullets = [b for job in master.experience for b in job.bullets]

    novelty: dict[str, float] = {}
    after: dict[str, int] = {}
    for level in ("reshape", "major", "max_ats"):
        tailored = await provider.tailor_cv(JD, analysis, master, "en", level)
        bullets = [b for job in tailored.experience for b in job.bullets]
        assert bullets, f"tailored CV ({level}) has no bullets"
        novelties = [metrics.bullet_novelty(b, master_bullets) for b in bullets]
        novelty[level] = sum(novelties) / len(novelties)
        after[level] = ats.score(analysis.keywords, tailored.plain_text())["score"]
        print(f"  {level}: mean novelty {novelty[level]:.2f}, ATS after {after[level]}%")

    ok = True
    ok &= _check("novelty ordering",
                 novelty["reshape"] < novelty["major"] <= novelty["max_ats"],
                 f"reshape {novelty['reshape']:.2f} < major {novelty['major']:.2f}"
                 f" <= max_ats {novelty['max_ats']:.2f}")
    ok &= _check("ATS after-score ordering",
                 after["max_ats"] >= after["major"] >= after["reshape"],
                 f"max_ats {after['max_ats']}% >= major {after['major']}%"
                 f" >= reshape {after['reshape']}%")
    return bool(ok)


async def main() -> int:
    settings = get_settings()
    if not settings.ai_enabled:
        print("SKIPPED: no Gemini key/Vertex configured.")
        return 0
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    provider = get_provider()
    master = CVData.model_validate_json((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))

    passed = 0
    for i in range(runs):
        print(f"run {i + 1}/{runs}")
        if await run_once(provider, master):
            passed += 1
    print("intensity matrix")
    matrix_ok = await run_intensity_matrix(provider, master)
    print(f"\n{passed}/{runs} runs passed; intensity matrix {'passed' if matrix_ok else 'failed'}")
    return 0 if passed == runs and matrix_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
