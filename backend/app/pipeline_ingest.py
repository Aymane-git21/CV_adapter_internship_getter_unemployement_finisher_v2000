"""Store fetched postings and open inbox applications, idempotently.

Two dedup layers:
1. (source, external_id) unique — the same offer re-polled is a no-op.
2. fuzzy (title, company) hash per user — the same job seen on a second
   board does not create a second inbox card.
"""
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ats import normalize
from .models import Application, JobPosting
from .schemas import JobPostingIn


def fuzzy_hash(title: str, company: str) -> str:
    key = normalize(title).strip() + "|" + normalize(company).strip()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


async def ingest(db: AsyncSession, user_id: int, postings: list[JobPostingIn]) -> int:
    new_applications = 0
    for p in postings:
        if not p.external_id or not p.title:
            continue
        existing = (
            await db.execute(
                select(JobPosting).where(
                    JobPosting.source == p.source, JobPosting.external_id == p.external_id
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = JobPosting(
                source=p.source, external_id=p.external_id, title=p.title,
                company=p.company, location=p.location, contract_type=p.contract_type,
                description=p.description, apply_email=p.apply_email, apply_url=p.apply_url,
                posted_at=p.posted_at, fuzzy_hash=fuzzy_hash(p.title, p.company), raw=p.raw,
            )
            db.add(existing)
            await db.flush()

        has_app = (
            await db.execute(
                select(Application.id)
                .join(JobPosting, Application.posting_id == JobPosting.id)
                .where(
                    Application.user_id == user_id,
                    JobPosting.fuzzy_hash == existing.fuzzy_hash,
                )
            )
        ).first()
        if has_app is None:
            db.add(Application(user_id=user_id, posting_id=existing.id))
            new_applications += 1
    return new_applications
