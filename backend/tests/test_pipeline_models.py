"""Tables and contracts for the auto-apply pipeline."""
import pytest
from sqlalchemy import select

from backend.app.db import session_factory
from backend.app.models import Application, JobPosting, SavedSearch, User
from backend.app.schemas import AnswersDoc, FactsProfile, JobPostingIn
from backend.tests.conftest import unique_email


def test_job_posting_in_defaults():
    p = JobPostingIn(source="ft", external_id="123", title="Dev Python", description="d" * 100)
    assert p.company == ""
    assert p.apply_email is None
    assert p.apply_url is None
    assert p.raw == {}


def test_facts_profile_defaults():
    f = FactsProfile()
    assert f.work_permit == ""
    assert f.notice_period == ""
    assert f.salary_range == ""
    assert AnswersDoc().items == []


async def test_pipeline_tables_roundtrip(client):
    async with session_factory()() as db:
        user = User(email=unique_email())
        db.add(user)
        await db.flush()
        search = SavedSearch(user_id=user.id, name="Toulouse ML", keywords="machine learning",
                             insee="31555", radius_km=20)
        db.add(search)
        await db.flush()
        posting = JobPosting(source="ft", external_id="FT-1", title="ML Engineer",
                             company="Lumina", description="desc", fuzzy_hash="abc")
        db.add(posting)
        await db.flush()
        app_row = Application(user_id=user.id, posting_id=posting.id)
        db.add(app_row)
        await db.commit()

        got = (await db.execute(select(Application).where(Application.user_id == user.id))).scalar_one()
        assert got.status == "inbox"
        assert got.audit == []
        # user columns added by _ensure_columns
        assert user.facts is None
        assert user.pipeline_enabled == 0
        assert user.gmail_refresh_token is None


async def test_posting_unique_per_source(client):
    from sqlalchemy.exc import IntegrityError
    async with session_factory()() as db:
        db.add(JobPosting(source="ft", external_id="DUP", title="A", description="x", fuzzy_hash="h1"))
        await db.commit()
    async with session_factory()() as db:
        db.add(JobPosting(source="ft", external_id="DUP", title="B", description="y", fuzzy_hash="h2"))
        with pytest.raises(IntegrityError):
            await db.commit()
