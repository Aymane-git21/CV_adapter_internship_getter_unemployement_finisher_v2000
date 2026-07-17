"""Periodic eval, paid lane (up to ~12 flash calls per run).

Can Gemini edit raw Typst source and have it compile? Typst is young and
sparse in training data, so source-mode edits lean on the injected primer
(backend/app/ai/typst_ref.py). This eval mirrors the production chat
pipeline exactly: edit -> compile -> one repair round with compiler
diagnostics -> compile. Scoring is deterministic: compile results plus
string checks on the edited source.

Run: python -m backend.evals.eval_source_edit
Exit 0 = pass (or SKIPPED without a key), 1 = fail.
"""
import asyncio
import sys
from pathlib import Path

from backend.app.ai import get_provider
from backend.app.config import get_settings
from backend.app.schemas import CVData
from backend.app.typstsvc import renderer

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

# (instruction, deterministic check on the edited source)
CASES = [
    ("Set the accent color to #0E8A66.",
     lambda s: "0E8A66" in s.upper()),
    ("Set font_scale to 1.15 so the whole document is a bit larger.",
     lambda s: "1.15" in s),
    ("Delete the Data Scientist experience entry entirely.",
     lambda s: "Data Scientist" not in s),
    ('Add this bullet to the first experience entry: "Migrated the CI pipeline to GitHub Actions".',
     lambda s: "GitHub Actions" in s),
    ("Switch the template to compact.",
     lambda s: "/typst/cv_compact.typ" in s),
    ("Render the candidate name in dark red.",
     lambda s: True),  # styling freedom; compiling is the bar
    # Harder, structural cases — where LaTeX habits or literal-syntax slips
    # (single-element arrays, nested dicts, markup after #render) break compiles.
    ("Add a new experience entry at the top: DevOps Intern at OVHcloud, Roubaix, "
     "Jan 2020 - Jun 2020, with one bullet: Automated bare-metal provisioning with Ansible.",
     lambda s: "OVHcloud" in s),
    ("Add a skills category named 'Languages & Frameworks' containing only C#.",
     lambda s: "C#" in s),
    ("Add a thin horizontal rule and the centered text 'References available upon "
     "request' at the very bottom of the document.",
     lambda s: "References available upon request" in s),
    ("Make all section headings smaller, uppercase, with wider letter spacing.",
     lambda s: True),  # styling freedom; compiling is the bar
]

# All cases must compile after at most one repair; semantic slack of one
# case absorbs benign phrasing choices, compile failures absorb nothing.
MIN_SEMANTIC = len(CASES) - 1


async def main() -> int:
    settings = get_settings()
    if not settings.ai_enabled:
        print("SKIPPED: no Gemini key/Vertex configured.")
        return 0
    provider = get_provider()
    master = CVData.model_validate_json((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))
    doc_settings = {"template": "onyx", "accent": "#0F62FE", "density": "normal",
                    "show_photo": False, "font_scale": 1.0, "lang": "en"}
    base_source = renderer.render_source("cv", "onyx", master.model_dump(), doc_settings, has_photo=False)

    first_pass = 0
    final_pass = 0
    semantic = 0
    for i, (instruction, check) in enumerate(CASES, 1):
        edited = await provider.edit_source(base_source, instruction)
        result = await renderer.compile_source(edited, fmt="svg")
        repaired = False
        if result.ok:
            first_pass += 1
        else:
            edited = await provider.repair_source(edited, result.diagnostics)
            result = await renderer.compile_source(edited, fmt="svg")
            repaired = True
        ok = result.ok
        sem = ok and check(edited)
        final_pass += ok
        semantic += sem
        print(f"  case {i}: compile={'ok' if ok else 'FAIL'}"
              f"{' (after repair)' if repaired and ok else ''}"
              f" semantic={'ok' if sem else 'FAIL'}  [{instruction[:60]}]")
        if not ok:
            print(f"    diagnostics: {result.diagnostics[:300]}")

    print(f"\nfirst-pass compile {first_pass}/{len(CASES)}, "
          f"final compile {final_pass}/{len(CASES)}, semantic {semantic}/{len(CASES)}")
    ok = final_pass == len(CASES) and semantic >= MIN_SEMANTIC
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
