"""poll_once fans a saved search across sources; the internal endpoint is token-guarded."""
import httpx
import pytest

from backend.app import poller
from backend.app.db import session_factory
from backend.app.models import SavedSearch, User
from backend.app.schemas import JobPostingIn, SavedSearchParams
from backend.tests.conftest import unique_email


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
    assert result["errors"] == ["adzuna down"]

    # Second run: idempotent.
    result2 = await poller.poll_once()
    assert result2["new"] == 0


async def test_internal_poll_requires_token(client, monkeypatch):
    monkeypatch.setattr(poller, "build_sources", lambda: [])
    r = await client.post("/api/internal/poll")
    assert r.status_code == 403
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "internal_token", "sekrit", raising=False)
    r2 = await client.post("/api/internal/poll", headers={"X-Internal-Token": "sekrit"})
    assert r2.status_code == 200
    assert set(r2.json()) == {"new", "errors"}
