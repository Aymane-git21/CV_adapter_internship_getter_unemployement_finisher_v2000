"""Review-queue API. The queue is the product: nothing sends without an
explicit approve, and nothing sends past the daily cap."""
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import REPO_ROOT, get_settings
from ..db import get_db
from ..jobs import spawn_job
from ..mailer import EmlSender, GmailSender, build_application_email
from ..models import Application, Document, Job, JobPosting, MasterCV, SavedSearch, User
from ..pipeline_states import advance
from ..quota import check_quota
from ..security import get_byok_key, get_current_user

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


async def require_pipeline_user(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Log in first.")
    if not user.pipeline_enabled:
        raise HTTPException(status_code=403, detail="The pipeline is not enabled for this account.")
    return user


class SearchIn(BaseModel):
    name: str = "Search"
    keywords: str = ""
    insee: str = ""
    radius_km: int = 20
    contract_type: str = ""


class PipelineGenerateIn(BaseModel):
    """Local model — deliberately NOT schemas.GenerateIn (different contract)."""

    application_ids: list[int] = Field(min_length=1)
    template: str = "onyx"
    accent: str = "#0F62FE"
    language: str = "fr"
    rewrite_intensity: str = "major"


class SendIn(BaseModel):
    subject: str | None = None
    body: str | None = None


def _app_payload(a: Application, p: JobPosting) -> dict:
    return {
        "id": a.id, "status": a.status, "job_id": a.job_id,
        "sent_via": a.sent_via, "sent_at": a.sent_at.isoformat() if a.sent_at else None,
        "audit": a.audit or [],
        "posting": {
            "id": p.id, "title": p.title, "company": p.company, "location": p.location,
            "source": p.source, "apply_email": p.apply_email, "apply_url": p.apply_url,
            "posted_at": p.posted_at, "contract_type": p.contract_type,
        },
    }


async def _get_app(db: AsyncSession, app_id: int, user: User) -> tuple[Application, JobPosting]:
    row = (
        await db.execute(
            select(Application, JobPosting)
            .join(JobPosting, Application.posting_id == JobPosting.id)
            .where(Application.id == app_id, Application.user_id == user.id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return row


@router.get("")
async def board(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    rows = (
        await db.execute(
            select(Application, JobPosting)
            .join(JobPosting, Application.posting_id == JobPosting.id)
            .where(Application.user_id == user.id)
            .order_by(Application.created_at.desc())
        )
    ).all()
    return {"applications": [_app_payload(a, p) for a, p in rows]}


@router.get("/searches")
async def list_searches(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> list[dict]:
    rows = (await db.execute(select(SavedSearch).where(SavedSearch.user_id == user.id))).scalars()
    return [
        {"id": s.id, "name": s.name, "keywords": s.keywords, "insee": s.insee,
         "radius_km": s.radius_km, "contract_type": s.contract_type, "enabled": s.enabled}
        for s in rows
    ]


@router.post("/searches")
async def create_search(
    body: SearchIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    s = SavedSearch(user_id=user.id, **body.model_dump())
    db.add(s)
    await db.commit()
    return {"id": s.id}


@router.delete("/searches/{search_id}")
async def delete_search(
    search_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    s = await db.get(SavedSearch, search_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Search not found.")
    await db.delete(s)
    await db.commit()
    return {"ok": True}


@router.post("/generate")
async def generate_for_applications(
    body: PipelineGenerateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
    byok: Annotated[str | None, Depends(get_byok_key)],
) -> dict:
    cv = (
        await db.execute(
            select(MasterCV).where(MasterCV.user_id == user.id)
            .order_by(MasterCV.is_default.desc(), MasterCV.updated_at.desc())
        )
    ).scalars().first()
    if cv is None or cv.data is None:
        raise HTTPException(status_code=404, detail="Save a master CV first.")

    # double-click safe: silent order-preserving dedupe
    application_ids = list(dict.fromkeys(body.application_ids))

    apps: list[tuple[Application, JobPosting]] = []
    for app_id in application_ids:
        a, p = await _get_app(db, app_id, user)
        if a.status != "inbox":
            raise HTTPException(status_code=409, detail=f"Application {app_id} is not in the inbox.")
        apps.append((a, p))

    await check_quota(db, user, None, len(apps), byok is not None, body.template)

    language = body.language if body.language in ("en", "fr", "de") else "fr"
    intensity = body.rewrite_intensity if body.rewrite_intensity in ("reshape", "minor", "major", "max_ats") else "major"
    job_ids: list[str] = []
    for a, p in apps:
        gen_params = {
            "master_data": cv.data, "photo_id": None, "template": body.template,
            "accent": body.accent, "show_photo": False, "intensity": intensity,
            "posting_id": p.id,
        }
        job = Job(
            id=uuid.uuid4().hex, user_id=user.id, language=language,
            job_description=p.description, byok=byok is not None, events=[],
            gen_params=gen_params,
        )
        db.add(job)
        a.job_id = job.id
        advance(a, "generated", note=f"job {job.id}")
        job_ids.append(job.id)
    await db.commit()

    for jid in job_ids:
        spawn_job(jid, cv.data, None, body.template, body.accent, False, byok, intensity)
    return {"jobs": job_ids}


@router.post("/{app_id}/approve")
async def approve(
    app_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    a, p = await _get_app(db, app_id, user)
    try:
        advance(a, "approved")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    return _app_payload(a, p)


class RejectIn(BaseModel):
    note: str = ""


@router.post("/{app_id}/reject")
async def reject(
    app_id: int,
    body: RejectIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    a, p = await _get_app(db, app_id, user)
    try:
        advance(a, "rejected", note=body.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    return _app_payload(a, p)


@router.post("/{app_id}/mark-sent")
async def mark_sent(
    app_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    a, p = await _get_app(db, app_id, user)
    try:
        advance(a, "sent", note="applied manually via link")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    a.sent_via = "manual"
    a.sent_at = datetime.now(UTC)
    await db.commit()
    return _app_payload(a, p)


async def _sent_today(db: AsyncSession, user_id: int) -> int:
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        await db.execute(
            select(func.count(Application.id)).where(
                Application.user_id == user_id,
                Application.sent_at >= day_start,
                Application.sent_via.in_(("gmail", "eml")),
            )
        )
    ).scalar_one()


@router.post("/{app_id}/send")
async def send(
    app_id: int,
    body: SendIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    a, p = await _get_app(db, app_id, user)
    if a.status != "approved":
        raise HTTPException(status_code=409, detail="Approve the application first.")
    if not p.apply_email:
        raise HTTPException(
            status_code=409,
            detail="This posting has no application email. Open the posting link and use mark-sent.",
        )
    settings = get_settings()
    if await _sent_today(db, user.id) >= settings.send_cap_daily:
        raise HTTPException(status_code=429, detail=f"Daily send cap reached ({settings.send_cap_daily}).")

    docs = (
        await db.execute(select(Document).where(Document.job_id == a.job_id))
    ).scalars().all()
    cv_doc = next((d for d in docs if d.kind == "cv"), None)
    letter_doc = next((d for d in docs if d.kind == "letter"), None)
    msg_doc = next((d for d in docs if d.kind == "message"), None)
    if cv_doc is None or cv_doc.pdf is None or letter_doc is None or letter_doc.pdf is None:
        raise HTTPException(status_code=409, detail="Documents are not ready for this application.")

    full_name = (cv_doc.data or {}).get("full_name", "") or user.email
    safe_name = full_name.replace(" ", "_") or "Candidate"
    subject = body.subject or f"Candidature - {p.title}" + (f" - {full_name}" if full_name else "")
    email_body = body.body or (msg_doc.text_content if msg_doc else "") or "Veuillez trouver ma candidature ci-jointe."
    msg = build_application_email(
        sender=user.email, to=p.apply_email, subject=subject, body=email_body,
        attachments=[(f"CV_{safe_name}.pdf", cv_doc.pdf), (f"Lettre_{safe_name}.pdf", letter_doc.pdf)],
    )
    if user.gmail_refresh_token:
        sender = GmailSender(user.gmail_refresh_token, settings.google_client_id, settings.google_client_secret)
        via = "gmail"
    else:
        sender = EmlSender(settings.eml_out_dir or str(REPO_ROOT / "eml_out"))
        via = "eml"
    try:
        await sender.send(msg)
    except Exception as exc:  # GmailError or IO — the row stays approved for an explicit retry
        raise HTTPException(status_code=502, detail=f"Send failed: {exc}") from exc
    advance(a, "sent", note=f"via {via} to {p.apply_email}")
    a.sent_via = via
    a.sent_at = datetime.now(UTC)
    await db.commit()
    return _app_payload(a, p)
