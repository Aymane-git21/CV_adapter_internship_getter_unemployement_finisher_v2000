"""Live smoke test of the Gemini provider (costs a few flash calls).
Run: python -m backend.scripts.smoke_gemini
"""
import asyncio
import json
from pathlib import Path

from backend.app.ai import get_provider
from backend.app.config import get_settings
from backend.app.schemas import CVData
from backend.app.typstsvc import renderer

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

JD = """Machine Learning Engineer — Hermès DSI Groupe (Pantin)
Concevoir les architectures de solutions IA de bout en bout : choix du modèle LLM,
vector stores, patterns d'intégration RAG, exposition API. Piloter le delivery des
projets IA avec les Data Scientists et le Lead ML Engineer. 5 ans d'expérience en
ingénierie IA, maîtrise des architectures cloud (GCP), expertise LLM : RAG, agents,
function calling, évaluation. Pratiques MLOps : monitoring, drift, rollback."""


async def main():
    settings = get_settings()
    print(f"ai_enabled={settings.ai_enabled} model={settings.gemini_model}")
    if not settings.ai_enabled:
        print("No real key configured — nothing to smoke test.")
        return

    provider = get_provider()
    master = CVData.model_validate_json((FIXTURES / "sample_cv.json").read_text(encoding="utf-8"))

    print("1) analyze…")
    analysis = await provider.analyze(JD, master.plain_text(), "fr")
    print(f"   title={analysis.job_title!r} company={analysis.company!r} kw={len(analysis.keywords)}")
    assert analysis.keywords, "no keywords extracted"

    print("2) tailor_cv + write_letter + outreach in parallel…")
    cv, letter, msg = await asyncio.gather(
        provider.tailor_cv(JD, analysis, master, "fr"),
        provider.write_letter(JD, analysis, master, "fr"),
        provider.outreach(JD, analysis, master, "fr"),
    )
    print(f"   cv.headline={cv.headline!r}")
    print(f"   letter.subject={letter.subject!r} paragraphs={len(letter.paragraphs)}")
    print(f"   outreach={msg[:90]!r}…")
    assert cv.experience and letter.paragraphs

    print("3) compile tailored CV…")
    doc_settings = {"template": "onyx", "accent": "#0F62FE", "density": "normal",
                    "show_photo": False, "font_scale": 1.0, "lang": "fr"}
    result, _ = await renderer.compile_document("cv", "onyx", cv.model_dump(), doc_settings, fmt="pdf")
    assert result.ok, result.diagnostics
    out = FIXTURES.parent / "smoke_cv.pdf"
    out.write_bytes(result.pdf)
    print(f"   OK — {len(result.pdf)} bytes -> {out}")

    print("\nSMOKE TEST PASSED")
    print(json.dumps({"keywords": [k.term for k in analysis.keywords][:8]}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
