"""France Travail adapter against recorded fixtures (no live HTTP)."""
import json
from pathlib import Path

import httpx
import pytest

from backend.app.schemas import SavedSearchParams
from backend.app.sources import SourceError
from backend.app.sources.france_travail import SEARCH_URL, TOKEN_URL, FranceTravailSource

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "france_travail_search.json").read_text(encoding="utf-8")
)


def _transport(search_status=200, search_json=None):
    calls = {"token": 0, "search": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(TOKEN_URL):
            calls["token"] += 1
            assert request.method == "POST"
            body = request.content.decode()
            assert "client_credentials" in body and "api_offresdemploiv2" in body
            return httpx.Response(200, json={"access_token": "tok-123", "expires_in": 1499})
        calls["search"] += 1
        assert request.headers["Authorization"] == "Bearer tok-123"
        params = dict(request.url.params)
        assert params["motsCles"] == "machine learning"
        assert params["commune"] == "31555"
        assert params["distance"] == "20"
        return httpx.Response(search_status, json=search_json if search_json is not None else FIXTURE)

    return httpx.MockTransport(handler), calls


async def test_fetch_normalizes_offers():
    transport, calls = _transport()
    src = FranceTravailSource(client_id="cid", client_secret="sec")
    async with httpx.AsyncClient(transport=transport) as client:
        postings = await src.fetch(
            SavedSearchParams(keywords="machine learning", insee="31555", radius_km=20), client
        )
    assert calls == {"token": 1, "search": 1}
    assert len(postings) == 2
    first = postings[0]
    assert first.source == "ft"
    assert first.external_id == "185XKPT"
    assert first.title == "Ingénieur Machine Learning (H/F)"
    assert first.company == "LUMINA AI"
    assert first.location == "31 - TOULOUSE"
    assert first.contract_type == "CDI"
    assert first.apply_email == "recrutement@lumina.example"
    second = postings[1]
    assert second.apply_email is None
    assert second.apply_url == "https://aerotech.example/careers/data-engineer"


async def test_search_failure_raises_source_error():
    transport, _ = _transport(search_status=500, search_json={"error": "boom"})
    src = FranceTravailSource(client_id="cid", client_secret="sec")
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(SourceError):
            await src.fetch(SavedSearchParams(keywords="machine learning", insee="31555"), client)


async def test_missing_credentials_raise_before_any_call():
    src = FranceTravailSource(client_id="", client_secret="")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as client:
        with pytest.raises(SourceError):
            await src.fetch(SavedSearchParams(keywords="x"), client)
