"""Account utilities: history, feedback, BYOK validation, public config."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import Document, FeedbackEntry, Job, User
from ..quota import ALL_TEMPLATES, PLANS
from ..schemas import ByokValidateIn, FeedbackIn
from ..security import require_user

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/config")
async def public_config():
    settings = get_settings()
    return {
        "billing_enabled": settings.billing_enabled,
        "google_client_id": settings.google_client_id or None,
        "adsense_client": settings.adsense_client or None,
        "ai_mode": "gemini" if settings.ai_enabled else "offline",
        "byok_enabled": True,
        "templates": [
            {"id": "onyx", "label": "Onyx", "vibe": "Modern · Sans", "default_accent": "#0F62FE"},
            {"id": "classic", "label": "Classic", "vibe": "Traditional · Serif", "default_accent": "#1C3B5A"},
            {"id": "compact", "label": "Compact", "vibe": "Dense · Engineering", "default_accent": "#0E8A66"},
        ],
        "plans": [
            {
                "key": p.key, "label": p.label, "daily": p.daily, "parallel": p.parallel,
                "templates": list(p.templates), "price_eur": p.price_eur,
            }
            for p in PLANS.values()
            if p.key != "guest"
        ],
        "all_templates": ALL_TEMPLATES,
    }


@router.get("/history")
async def history(
    user: Annotated[User, Depends(require_user)], db: Annotated[AsyncSession, Depends(get_db)]
):
    jobs = (
        (
            await db.execute(
                select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(100)
            )
        )
        .scalars().all()
    )
    job_ids = [j.id for j in jobs]
    docs: dict[str, list[Document]] = {}
    if job_ids:
        rows = (
            (await db.execute(select(Document).where(Document.job_id.in_(job_ids))))
            .scalars().all()
        )
        for d in rows:
            docs.setdefault(d.job_id, []).append(d)
    out = []
    for j in jobs:
        jd_docs = sorted(docs.get(j.id, []), key=lambda d: d.kind)
        cv_doc = next((d for d in jd_docs if d.kind == "cv"), None)
        out.append(
            {
                "id": j.id,
                "status": j.status,
                "title": j.title or "Generation",
                "company": j.company,
                "language": j.language,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "score_before": cv_doc.score_before if cv_doc else None,
                "score_after": cv_doc.score_after if cv_doc else None,
                "documents": [
                    {"id": d.id, "kind": d.kind, "title": d.title} for d in jd_docs
                ],
            }
        )
    return out


@router.post("/feedback")
async def feedback(body: FeedbackIn, db: Annotated[AsyncSession, Depends(get_db)]):
    db.add(FeedbackEntry(name=body.name[:120], email=body.email[:255], message=body.message))
    await db.commit()
    return {"ok": True}


@router.post("/byok/validate")
async def byok_validate(body: ByokValidateIn):
    from ..ai.gemini import GeminiProvider

    if not body.key.startswith("AIza"):
        raise HTTPException(status_code=422, detail="That does not look like a Gemini API key (AIza…).")
    provider = GeminiProvider(api_key=body.key)
    ok = await provider.validate_key()
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Gemini rejected this key. Create one at aistudio.google.com/apikey and try again.",
        )
    return {"ok": True}
