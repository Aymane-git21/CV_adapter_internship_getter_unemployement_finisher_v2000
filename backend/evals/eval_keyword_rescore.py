"""Periodic eval, paid lane (1 analyze + 1 tailor + 2 edit calls per run).

Does the keyword match move the way a user expects when the ASSISTANT edits
the CV? The chat edit is latent (the model rewrites the CV JSON); the
re-score is deterministic (backend/app/doctext.py + backend/app/ats.py). This
runs the production pair on the real model: ask the assistant to remove the
heaviest matched keyword, then to add it back, and check the score and the
matched/missing lists follow each edit.

Run: python -m backend.evals.eval_keyword_rescore
Exit 0 = pass (or SKIPPED without a key), 1 = fail.
"""
import asyncio
import sys
from pathlib import Path

from backend.app import ats, doctext
from backend.app.ai import get_provider
from backend.app.config import get_settings
from backend.app.schemas import CVData
from backend.app.typstsvc import renderer
from backend.evals.eval_tailor_boost import JD

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

# A removal instruction should cost the one keyword it names; losing one more
# match as collateral (a bullet that named two tools) is tolerated.
MAX_COLLATERAL_LOSSES = 1


def _check(name: str, ok: bool, detail: str) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    return ok


def _score(keywords, cv: CVData) -> dict:
    return ats.score(keywords, doctext.cv_text(cv.model_dump()))


async def run(provider, master: CVData) -> bool:
    analysis = await provider.analyze(JD, master.plain_text(), "en")
    tailored = await provider.tailor_cv(JD, analysis, master, "en", "max_ats")
    base = _score(analysis.keywords, tailored)
    print(f"  tailored: {base['score']}%  missing={base['missing']}")
    if not base["matched"]:
        return _check("something to remove", False, "the tailored CV matched no keyword")

    weights = {k.term: k.weight for k in analysis.keywords}
    term = max(base["matched"], key=lambda t: weights.get(t, 1))
    kw = next(k for k in analysis.keywords if k.term == term)
    spellings = ", ".join(f'"{s}"' for s in [kw.term, *kw.aliases])

    removed = await provider.edit_cv_data(
        tailored, f"Remove every mention of {spellings} from the CV, wherever it appears.", "en"
    )
    after_remove = _score(analysis.keywords, removed)
    restored = await provider.edit_cv_data(
        removed, f'Add "{term}" to the most relevant skills group.', "en"
    )
    after_add = _score(analysis.keywords, restored)
    collateral = sorted(set(base["matched"]) - {term} - set(after_remove["matched"]))

    ok = True
    ok &= _check("removal moves the keyword to missing", term in after_remove["missing"],
                 f"{term!r} missing={after_remove['missing']}")
    ok &= _check("removal lowers the score", after_remove["score"] < base["score"],
                 f"{base['score']}% -> {after_remove['score']}%")
    ok &= _check("removal spares the other matches", len(collateral) <= MAX_COLLATERAL_LOSSES,
                 f"collateral losses {collateral or 'none'} (max {MAX_COLLATERAL_LOSSES})")
    ok &= _check("re-adding moves it back to matched", term in after_add["matched"],
                 f"{term!r} matched={after_add['matched']}")
    ok &= _check("re-adding raises the score", after_add["score"] > after_remove["score"],
                 f"{after_remove['score']}% -> {after_add['score']}%")
    # The source editor must read what the form reads, on real model output too.
    source = renderer.render_source("cv", "onyx", restored.model_dump(), {"lang": "en"}, has_photo=False)
    same = doctext.typst_source_text(source) == doctext.cv_text(restored.model_dump())
    ok &= _check("typst source text equals data text", same, "identical" if same else "diverged")
    return bool(ok)


async def main() -> int:
    if not get_settings().ai_enabled:
        print("SKIPPED: no Gemini key/Vertex configured.")
        return 0
    master = CVData.model_validate_json((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))
    print("keyword re-score after assistant edits")
    ok = await run(get_provider(), master)
    print(f"\n{'passed' if ok else 'failed'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
