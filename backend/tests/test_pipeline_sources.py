"""Adapter registry. Concrete adapter tests live in their own files."""
import httpx
import pytest

from backend.app.schemas import JobPostingIn, SavedSearchParams
from backend.app.sources import SourceError, all_sources, get_source, register


@pytest.fixture(autouse=True)
def _clean_registry():
    from backend.app.sources import _REGISTRY
    saved = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(saved)


class DummySource:
    name = "dummy"

    async def fetch(self, params: SavedSearchParams, client: httpx.AsyncClient):
        return [JobPostingIn(source=self.name, external_id="1", title="T", description="D")]


def test_register_and_get():
    register(DummySource())
    assert get_source("dummy").name == "dummy"
    assert any(s.name == "dummy" for s in all_sources())


def test_get_unknown_raises():
    with pytest.raises(SourceError):
        get_source("nope")
