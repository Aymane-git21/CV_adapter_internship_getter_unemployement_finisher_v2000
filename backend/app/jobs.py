"""Generation pipeline and in-process job runner.

Job state lives in the database (works with any worker count and across
Cloud Run instances); execution is asyncio tasks in the instance that
accepted the request. SSE readers poll the DB, so any instance can serve
progress for any job.
"""
import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from . import ats
from .ai import get_provider
from .ai.base import AIError
from .config import get_settings
from .db import session_factory
from .models import Document, Job, Photo
from .schemas import CVData, DocSettings, JobAnalysis, LetterData
from .typstsvc import renderer

log = logging.getLogger(__name__)

_job_semaphore: asyncio.Semaphore | None = None
_FR_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
_EN_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _sem() -> asyncio.Semaphore:
    global _job_semaphore
    if _job_semaphore is None:
        _job_semaphore = asyncio.Semaphore(get_settings().job_concurrency)
    return _job_semaphore


def letter_date(language: str, city: str) -> str:
    now = datetime.now(UTC)
    if language == "fr":
        base = f"le {now.day} {_FR_MONTHS[now.month - 1]} {now.year}"
        return f"{city}, {base}" if city else base.capitalize()
    base = f"{_EN_MONTHS[now.month - 1]} {now.day}, {now.year}"
    return f"{city}, {base}" if city else base


async def _emit(db: AsyncSession, job: Job, step: str, message: str, pct: int) -> None:
    events = list(job.events or [])
    events.append(
        {"ts": datetime.now(UTC).isoformat(), "step": step, "message": message, "pct": pct}
    )
    job.events = events
    await db.commit()


def spawn_job(
    job_id: str,
    master_data: dict,
    photo_id: str | None,
    template: str,
    accent: str,
    show_photo: bool,
    byok_key: str | None,
) -> None:
    """Fire-and-forget; all state lands in the DB."""
    asyncio.create_task(
        _run_job_safely(job_id, master_data, photo_id, template, accent, show_photo, byok_key)
    )


async def _run_job_safely(*args) -> None:
    async with _sem():
        try:
            await _run_job(*args)
        except Exception:  # pragma: no cover — last-resort guard
            log.exception("job runner crashed")


async def _run_job(
    job_id: str,
    master_data: dict,
    photo_id: str | None,
    template: str,
    accent: str,
    show_photo: bool,
    byok_key: str | None,
) -> None:
    async with session_factory()() as db:
        job = await db.get(Job, job_id)
        if job is None:
            return
        try:
            await _pipeline(db, job, master_data, photo_id, template, accent, show_photo, byok_key)
        except AIError as exc:
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = datetime.now(UTC)
            await _emit(db, job, "failed", str(exc), 100)
        except Exception as exc:
            log.exception("job %s failed", job_id)
            job.status = "failed"
            job.error = "Internal error while generating. Please try again."
            job.finished_at = datetime.now(UTC)
            await _emit(db, job, "failed", f"Internal error: {type(exc).__name__}", 100)


async def _pipeline(
    db: AsyncSession,
    job: Job,
    master_data: dict,
    photo_id: str | None,
    template: str,
    accent: str,
    show_photo: bool,
    byok_key: str | None,
) -> None:
    provider = get_provider(byok_key)
    language = job.language
    master = CVData.model_validate(master_data)

    job.status = "running"
    await _emit(db, job, "analyze", "Scanning the job description like a recruiter would…", 8)

    analysis: JobAnalysis = await provider.analyze(job.job_description, master.plain_text(), language)
    job.title = analysis.job_title
    job.company = analysis.company
    job.analysis = analysis.model_dump()
    before = ats.score(analysis.keywords, master.plain_text())
    await _emit(
        db, job, "analyzed",
        f"Found {len(analysis.keywords)} key requirements — current match {before['score']}%.", 22,
    )

    await _emit(db, job, "generate", "Tailoring CV, cover letter and outreach in parallel…", 30)
    cv_task = provider.tailor_cv(job.job_description, analysis, master, language)
    letter_task = provider.write_letter(job.job_description, analysis, master, language)
    msg_task = provider.outreach(job.job_description, analysis, master, language)
    tailored, letter, message = await asyncio.gather(cv_task, letter_task, msg_task)

    after = ats.score(analysis.keywords, tailored.plain_text())
    await _emit(
        db, job, "generated",
        f"Content ready — keyword match {before['score']}% → {after['score']}%.", 62,
    )

    # Deterministic letter fields the model must not control.
    city = (master.contacts.location or "").split(",")[0].strip()
    letter.sender = LetterData().sender.model_copy(
        update={
            "full_name": master.full_name,
            "email": master.contacts.email,
            "phone": master.contacts.phone,
            "location": master.contacts.location,
        }
    )
    letter.date_str = letter_date(language, city)
    letter.signature = master.full_name

    # ---- Render & compile -----------------------------------------------------
    await _emit(db, job, "render", "Typesetting documents (Typst engine)…", 72)
    photo_bytes: bytes | None = None
    if show_photo and photo_id:
        photo = await db.get(Photo, photo_id)
        if photo is not None:
            photo_bytes = photo.content

    doc_settings = DocSettings(
        template=template, accent=accent, density="normal",
        show_photo=bool(photo_bytes), lang=language,
    ).model_dump()

    cv_result, cv_source = await renderer.compile_document(
        "cv", template, tailored.model_dump(), doc_settings, photo=photo_bytes, fmt="pdf"
    )
    letter_result, letter_source = await renderer.compile_document(
        "letter", template, letter.model_dump(), doc_settings, photo=None, fmt="pdf"
    )
    if not cv_result.ok or not letter_result.ok:
        diag = cv_result.diagnostics or letter_result.diagnostics
        raise AIError(f"Document rendering failed: {diag[:300]}")

    cv_settings = {**doc_settings, "density": cv_result.density_used}
    title = f"{analysis.job_title}" + (f" — {analysis.company}" if analysis.company else "")

    cv_doc = Document(
        id=uuid.uuid4().hex, job_id=job.id, user_id=job.user_id, kind="cv",
        title=title, template_id=template, settings=cv_settings,
        data=tailored.model_dump(), source=cv_source, mode="data",
        photo_id=photo_id if photo_bytes else None, pdf=cv_result.pdf,
        score_before=before["score"], score_after=after["score"],
        keywords={"matched": after["matched"], "missing": after["missing"]},
    )
    letter_doc = Document(
        id=uuid.uuid4().hex, job_id=job.id, user_id=job.user_id, kind="letter",
        title=title, template_id=template, settings=doc_settings,
        data=letter.model_dump(), source=letter_source, mode="data",
        pdf=letter_result.pdf,
    )
    msg_doc = Document(
        id=uuid.uuid4().hex, job_id=job.id, user_id=job.user_id, kind="message",
        title=title, template_id=template, settings=doc_settings,
        text_content=message, mode="data",
    )
    db.add_all([cv_doc, letter_doc, msg_doc])

    job.status = "completed"
    job.finished_at = datetime.now(UTC)
    await _emit(db, job, "done", "Documents ready.", 100)


def job_snapshot(job: Job, documents: list[Document] | None = None) -> dict:
    out = {
        "id": job.id,
        "status": job.status,
        "title": job.title,
        "company": job.company,
        "language": job.language,
        "events": job.events or [],
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
    if documents is not None:
        out["documents"] = [
            {
                "id": d.id,
                "kind": d.kind,
                "title": d.title,
                "template": d.template_id,
                "score_before": d.score_before,
                "score_after": d.score_after,
            }
            for d in documents
        ]
    return out
