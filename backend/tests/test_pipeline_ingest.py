"""Idempotent ingest: same poll twice = zero new rows; cross-source dupes collapse."""
import pytest
from sqlalchemy import func, select

from backend.app.db import session_factory
from backend.app.models import Application, JobPosting, User
from backend.app.pipeline_ingest import fuzzy_hash, ingest
from backend.app.schemas import JobPostingIn
from backend.tests.conftest import unique_email


def _posting(source="ft", ext="A1", title="ML Engineer", company="Lumina"):
    return JobPostingIn(source=source, external_id=ext, title=title, company=company,
                        description="desc long enough")


def test_fuzzy_hash_normalizes():
    assert fuzzy_hash("ML  Engineer (H/F)", "LUMINA") == fuzzy_hash("ml engineer h/f", "Lumina")
    assert fuzzy_hash("ML Engineer", "Lumina") != fuzzy_hash("Data Engineer", "Lumina")


async def test_ingest_idempotent(client):
    async with session_factory()() as db:
        user = User(email=unique_email())
        db.add(user)
        await db.commit()
        uid = user.id

    async with session_factory()() as db:
        n1 = await ingest(db, uid, [_posting(), _posting(ext="A2", title="Data Engineer")])
        await db.commit()
    async with session_factory()() as db:
        n2 = await ingest(db, uid, [_posting(), _posting(ext="A2", title="Data Engineer")])
        await db.commit()
        assert (n1, n2) == (2, 0)
        total = (await db.execute(select(func.count(Application.id)).where(Application.user_id == uid))).scalar_one()
        assert total == 2


async def test_cross_source_duplicate_collapses(client):
    async with session_factory()() as db:
        user = User(email=unique_email())
        db.add(user)
        await db.commit()
        uid = user.id

    async with session_factory()() as db:
        await ingest(db, uid, [_posting(source="ft", ext="F1")])
        await db.commit()
    async with session_factory()() as db:
        n = await ingest(db, uid, [_posting(source="adzuna", ext="Z9")])  # same title+company
        await db.commit()
        # Posting stored (different source id) but NO second application for the user.
        assert n == 0
        postings = (await db.execute(select(func.count(JobPosting.id)))).scalar_one()
        apps = (await db.execute(select(func.count(Application.id)).where(Application.user_id == uid))).scalar_one()
        assert postings >= 2 and apps == 1
