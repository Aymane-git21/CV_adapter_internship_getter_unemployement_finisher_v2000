"""Batch generation + job status + SSE progress stream."""
import asyncio
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai import get_provider
from ..ai.base import AIError
from ..db import get_db, session_factory
from ..jobs import job_snapshot, spawn_job
from ..models import Document, Job, MasterCV, User
from ..quota import check_quota
from ..schemas import GenerateIn
from ..security import get_byok_key, get_current_user, guest_key_hash

router = APIRouter(prefix="/api", tags=["generate"])

_MAX_JD_CHARS = 30_000


@router.post("/generate")
async def generate(
    body: GenerateIn,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(get_current_user)],
    byok: Annotated[str | None, Depends(get_byok_key)],
):
    jds = [jd.strip() for jd in body.job_descriptions if jd.strip()]
    if not jds:
        raise HTTPException(status_code=422, detail="Provide at least one job description.")
    if any(len(jd) > _MAX_JD_CHARS for jd in jds):
        raise HTTPException(status_code=422, detail="A job description exceeds 30k characters.")
    if any(len(jd) < 80 for jd in jds):
        raise HTTPException(
            status_code=422,
            detail="A job description looks too short. Paste the full posting (at least 80 characters).",
        )

    guest_hash = guest_key_hash(request) if user is None else None
    await check_quota(db, user, guest_hash, len(jds), byok is not None, body.template)

    # ---- Resolve the master CV ------------------------------------------------
    master_data: dict | None = None
    if body.master_cv_id is not None:
        if user is None:
            raise HTTPException(status_code=401, detail="Log in to use a saved CV.")
        cv = await db.get(MasterCV, body.master_cv_id)
        if cv is None or cv.user_id != user.id or cv.data is None:
            raise HTTPException(status_code=404, detail="Saved CV not found.")
        master_data = cv.data
    elif body.cv_text and body.cv_text.strip():
        try:
            parsed = await get_provider(byok).parse_cv(body.cv_text.strip(), None, body.language)
        except AIError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        master_data = parsed.model_dump()
        if user is not None and body.save_master:
            count = len((await db.execute(select(MasterCV.id).where(MasterCV.user_id == user.id))).all())
            db.add(
                MasterCV(
                    user_id=user.id, name="Imported CV", data=master_data,
                    raw_text=body.cv_text.strip(), is_default=count == 0,
                )
            )
    elif user is not None:
        cv = (
            await db.execute(
                select(MasterCV)
                .where(MasterCV.user_id == user.id)
                .order_by(MasterCV.is_default.desc(), MasterCV.updated_at.desc())
            )
        ).scalars().first()
        if cv is not None and cv.data is not None:
            master_data = cv.data
    if master_data is None:
        raise HTTPException(status_code=422, detail="No CV provided. Paste your CV or save one first.")

    # ---- Create job rows, then spawn ------------------------------------------
    language = body.language if body.language in ("en", "fr", "de") else "en"
    job_ids: list[str] = []
    for jd in jds:
        job = Job(
            id=uuid.uuid4().hex,
            user_id=user.id if user else None,
            language=language,
            job_description=jd,
            byok=byok is not None,
            events=[],
        )
        db.add(job)
        job_ids.append(job.id)
    await db.commit()

    for jid in job_ids:
        spawn_job(
            jid, master_data, body.photo_id, body.template, body.accent, body.show_photo, byok
        )
    return {"jobs": job_ids}


async def _load_snapshot(job_id: str) -> dict | None:
    async with session_factory()() as db:
        job = await db.get(Job, job_id)
        if job is None:
            return None
        docs = None
        if job.status in ("completed", "failed"):
            docs = (
                (await db.execute(select(Document).where(Document.job_id == job_id).order_by(Document.kind)))
                .scalars().all()
            )
        return job_snapshot(job, docs)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    snap = await _load_snapshot(job_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return snap


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    """Server-sent events: emits the job snapshot whenever it changes."""

    async def stream():
        last_payload = ""
        for _ in range(900):  # hard cap ~10.5 min
            if await request.is_disconnected():
                return
            snap = await _load_snapshot(job_id)
            if snap is None:
                yield f"data: {json.dumps({'status': 'unknown'})}\n\n"
                return
            payload = json.dumps(snap, ensure_ascii=False)
            if payload != last_payload:
                last_payload = payload
                yield f"data: {payload}\n\n"
            if snap["status"] in ("completed", "failed"):
                return
            await asyncio.sleep(0.7)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
