"""Adzuna FR adapter against recorded fixtures."""
import json
from pathlib import Path

import httpx
import pytest

from backend.app.schemas import SavedSearchParams
from backend.app.sources import SourceError
from backend.app.sources.adzuna import SEARCH_URL, AdzunaSource

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "adzuna_search.json").read_text(encoding="utf-8")
)


async def test_fetch_normalizes_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(SEARCH_URL)
        params = dict(request.url.params)
        assert params["app_id"] == "aid" and params["app_key"] == "akey"
        assert params["what"] == "python"
        assert params["where"] == "Toulouse"
        return httpx.Response(200, json=FIXTURE)

    src = AdzunaSource(app_id="aid", app_key="akey")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        postings = await src.fetch(SavedSearchParams(keywords="python", insee="31555"), client)
    assert len(postings) == 1
    p = postings[0]
    assert p.source == "adzuna"
    assert p.external_id == "5011223344"
    assert p.company == "Softlab"
    assert p.apply_email is None
    assert p.apply_url == "https://www.adzuna.fr/land/ad/5011223344"


async def test_error_status_raises():
    src = AdzunaSource(app_id="aid", app_key="akey")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(403, json={}))
    ) as client:
        with pytest.raises(SourceError):
            await src.fetch(SavedSearchParams(keywords="python"), client)


async def test_malformed_json_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    src = AdzunaSource(app_id="aid", app_key="akey")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError, match="Adzuna returned an unreadable response"):
            await src.fetch(SavedSearchParams(keywords="python"), client)
