"""Job-posting source adapters. Every adapter normalizes into JobPostingIn;
nothing downstream knows which board a posting came from. Server-side code
talks ONLY to official APIs — scraping bot-defended boards is out of scope
by design (see docs/superpowers/specs/2026-08-08-auto-apply-design.md)."""
from typing import Protocol

import httpx

from ..schemas import JobPostingIn, SavedSearchParams


class SourceError(Exception):
    """A source failed or is unknown; the poll survives and reports it."""


class SourceAdapter(Protocol):
    name: str

    async def fetch(
        self, params: SavedSearchParams, client: httpx.AsyncClient
    ) -> list[JobPostingIn]: ...


_REGISTRY: dict[str, SourceAdapter] = {}


def register(adapter: SourceAdapter) -> None:
    _REGISTRY[adapter.name] = adapter


def get_source(name: str) -> SourceAdapter:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise SourceError(f"Unknown source '{name}'") from exc


def all_sources() -> list[SourceAdapter]:
    return list(_REGISTRY.values())
