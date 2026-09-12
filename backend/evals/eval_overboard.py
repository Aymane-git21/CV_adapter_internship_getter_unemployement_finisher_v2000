"""Periodic eval, paid lane (1 analyze + 1 tailor call per run).

Overboard mode tells the model to fabricate whatever the posting asks for and
to place EVERY keyword. The 100% match itself is guaranteed deterministically
(ats.cover_all_keywords lists anything the model missed in skills), so this
eval measures what that backstop cannot: how much of the coverage the MODEL
delivers, how much of it lands in real prose instead of a skills dump, that
the mode actually invents rather than behaving like max_ats, and that the
invented CV stays usable (identity untouched, page budget, style rails).
All scoring is deterministic (ats, doctext, metrics); only generation is latent.

Run: python -m backend.evals.eval_overboard [runs]
Exit 0 = pass (or SKIPPED without a key), 1 = fail.
"""
import asyncio
import json
import sys
from pathlib import Path

from backend.app import ats, doctext
from backend.app.ai import get_provider
from backend.app.config import get_settings
from backend.app.schemas import CVData
from backend.evals import metrics
from backend.evals.eval_tailor_boost import JD

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

# Weighted keyword score of the model's own output, before the backstop runs.
MIN_MODEL_SCORE = 90
# Share of keywords written into prose (headline, summary, bullets, projects),
# not only listed in skills: a keyword dump is not a CV.
MIN_PROSE_SHARE = 0.60


def _check(name: str, ok: bool, detail: str) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    return ok


def _prose(cv: CVData) -> str:
    parts = [cv.headline, cv.summary]
    for job in cv.experience:
        parts += job.bullets
    for project in cv.projects:
        parts += [project.name, project.tech, project.description]
    return "\n".join(parts)


async def run_once(provider, master: CVData) -> bool:
    analysis = await provider.analyze(JD, master.plain_text(), "en")
    raw = await provider.tailor_cv(JD, analysis, master, "en", "overboard")
    final = ats.cover_all_keywords(analysis.keywords, raw, "en")

    total = len(analysis.keywords) or 1
    in_master = set(ats.score(analysis.keywords, doctext.cv_text(master.model_dump()))["matched"])
    model = ats.score(analysis.keywords, doctext.cv_text(raw.model_dump()))
    done = ats.score(analysis.keywords, doctext.cv_text(final.model_dump()))
    prose = ats.score(analysis.keywords, _prose(raw))
    absent_from_master = [k.term for k in analysis.keywords if k.term not in in_master]
    invented = sorted(set(prose["matched"]) - in_master)

    dump = raw.model_dump()
    master_json = json.dumps(master.model_dump(), ensure_ascii=False)
    lines, budget = metrics.content_lines(dump), metrics.content_line_budget(dump)
    em_dashes = metrics.em_dash_fields(dump, master_json)
    filler = metrics.filler_words(json.dumps(dump, ensure_ascii=False), master_json)

    ok = True
    ok &= _check("final keyword match", done["score"] == 100,
                 f"{done['score']}% (backstop added {model['missing'] or 'nothing'})")
    ok &= _check("model placed the keywords itself", model["score"] >= MIN_MODEL_SCORE,
                 f"{model['score']}% before the backstop (min {MIN_MODEL_SCORE}%)")
    ok &= _check("keywords land in prose", len(prose["matched"]) / total >= MIN_PROSE_SHARE,
                 f"{len(prose['matched'])}/{total} in headline/summary/bullets/projects "
                 f"(min {MIN_PROSE_SHARE:.0%})")
    ok &= _check("the mode invents", bool(invented) or not absent_from_master,
                 f"{invented or 'nothing'} written into prose, absent from the master "
                 f"({len(absent_from_master)} keywords were missing there)")
    ok &= _check("identity untouched",
                 raw.full_name == master.full_name and raw.contacts == master.contacts,
                 "full_name and contacts equal the master CV's")
    ok &= _check("one-page budget", lines <= budget, f"{lines} content lines, budget {budget}")
    ok &= _check("no em dash", not em_dashes, f"{em_dashes or 'clean'}")
    ok &= _check("no filler adjectives", not filler, f"{filler or 'clean'}")
    return bool(ok)


async def main() -> int:
    if not get_settings().ai_enabled:
        print("SKIPPED: no Gemini key/Vertex configured.")
        return 0
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    provider = get_provider()
    master = CVData.model_validate_json((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))
    passed = 0
    for i in range(runs):
        print(f"overboard run {i + 1}/{runs}")
        if await run_once(provider, master):
            passed += 1
    print(f"\n{passed}/{runs} runs passed")
    return 0 if passed == runs else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
