"""poll_once fans a saved search across sources; the internal endpoint is token-guarded."""
import httpx
import pytest
from sqlalchemy import update

from backend.app import poller
from backend.app.db import session_factory
from backend.app.models import SavedSearch, User
from backend.app.schemas import JobPostingIn, SavedSearchParams
from backend.tests.conftest import unique_email


async def _disable_other_searches(db):
    """poll_once() scans every enabled SavedSearch of every pipeline_enabled
    user, and the test DB is shared across this whole file's tests (no
    per-test reset) — so earlier tests' rows are still enabled and would be
    picked up too, making result["new"] counts order-dependent. Silence them
    before adding this test's own (default-enabled) SavedSearch."""
    await db.execute(update(SavedSearch).values(enabled=False))


class StubSource:
    def __init__(self, name, postings=None, error=None):
        self.name = name
        self._postings = postings or []
        self._error = error

    async def fetch(self, params: SavedSearchParams, client: httpx.AsyncClient):
        if self._error:
            raise self._error
        return self._postings


async def test_poll_once_ingests_and_survives_source_failure(client, monkeypatch):
    async with session_factory()() as db:
        await _disable_other_searches(db)
        user = User(email=unique_email(), pipeline_enabled=1)
        db.add(user)
        await db.flush()
        db.add(SavedSearch(user_id=user.id, name="ML", keywords="ml", insee="31555"))
        await db.commit()

    from backend.app.sources import SourceError
    good = StubSource("ft", postings=[
        JobPostingIn(source="ft", external_id="P1", title="ML Engineer", company="Lumina",
                     description="d"),
    ])
    bad = StubSource("adzuna", error=SourceError("adzuna down"))
    monkeypatch.setattr(poller, "build_sources", lambda: [good, bad])

    result = await poller.poll_once()
    assert result["new"] == 1
    assert result["errors"] == ["adzuna: adzuna down"]

    # Second run: idempotent.
    result2 = await poller.poll_once()
    assert result2["new"] == 0


async def test_poll_once_survives_ingest_failure(client, monkeypatch):
    async with session_factory()() as db:
        await _disable_other_searches(db)
        user = User(email=unique_email(), pipeline_enabled=1)
        db.add(user)
        await db.flush()
        db.add(SavedSearch(user_id=user.id, name="ML", keywords="ml", insee="31555"))
        await db.commit()

    good_ft = StubSource("ft", postings=[
        JobPostingIn(source="ft", external_id="IG1", title="ML Engineer", company="Lumina",
                     description="d"),
    ])
    good_adzuna = StubSource("adzuna", postings=[
        JobPostingIn(source="adzuna", external_id="IG2", title="Data Engineer", company="Lumina",
                     description="d"),
    ])
    monkeypatch.setattr(poller, "build_sources", lambda: [good_ft, good_adzuna])

    from backend.app.pipeline_ingest import ingest as real_ingest
    calls = {"n": 0}

    async def flaky_ingest(db, user_id, postings):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("ingest boom")
        return await real_ingest(db, user_id, postings)

    monkeypatch.setattr(poller, "ingest", flaky_ingest)

    result = await poller.poll_once()
    assert result["new"] == 1
    assert result["errors"] == ["ft: ingest boom"]

    # Second run with the real ingest restored: the rollback after the first
    # failure didn't poison the session, and the ft posting — never actually
    # ingested during the failed call — lands now.
    monkeypatch.setattr(poller, "ingest", real_ingest)
    result2 = await poller.poll_once()
    assert result2["new"] == 1


async def test_internal_poll_requires_token(client, monkeypatch):
    monkeypatch.setattr(poller, "build_sources", lambda: [])
    r = await client.post("/api/internal/poll")
    assert r.status_code == 403
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "internal_token", "sekrit", raising=False)
    r2 = await client.post("/api/internal/poll", headers={"X-Internal-Token": "sekrit"})
    assert r2.status_code == 200
    assert set(r2.json()) == {"new", "errors"}


async def test_internal_poll_rejects_wrong_token(client, monkeypatch):
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "internal_token", "sekrit", raising=False)
    r = await client.post("/api/internal/poll", headers={"X-Internal-Token": "wrong"})
    assert r.status_code == 403
