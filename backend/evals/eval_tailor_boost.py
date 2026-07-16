"""Periodic eval, paid lane (a few flash calls per run).

Measures whether tailor_cv actually REWRITES and boosts the CV instead of
transcribing the master, while inventing zero numbers. All scoring is
deterministic (backend/evals/metrics.py); only the generation is latent.

Run: python -m backend.evals.eval_tailor_boost [runs]
Exit 0 = pass (or no key configured, printed as SKIPPED), 1 = fail.
"""
import asyncio
import json
import sys
from pathlib import Path

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
    ok &= _check("no em dash", "—" not in tailored_text, "clean" if "—" not in tailored_text else "found")
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
    print(f"\n{passed}/{runs} runs passed")
    return 0 if passed == runs else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
