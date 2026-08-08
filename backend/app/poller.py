"""Scheduled posting fetch. Dev: an asyncio loop started from lifespan.
Prod: Cloud Scheduler POSTs /api/internal/poll with the internal token.
A failing source never kills the poll; its error is reported and the
other sources still land."""
import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from .config import get_settings
from .db import session_factory
from .models import SavedSearch, User
from .pipeline_ingest import ingest
from .schemas import SavedSearchParams
from .sources import SourceAdapter
from .sources.adzuna import AdzunaSource
from .sources.france_travail import FranceTravailSource

log = logging.getLogger(__name__)

internal_router = APIRouter(prefix="/api/internal", tags=["internal"])


def build_sources() -> list[SourceAdapter]:
    s = get_settings()
    out: list[SourceAdapter] = []
    if s.ft_client_id and s.ft_client_secret:
        out.append(FranceTravailSource(s.ft_client_id, s.ft_client_secret))
    if s.adzuna_app_id and s.adzuna_app_key:
        out.append(AdzunaSource(s.adzuna_app_id, s.adzuna_app_key))
    return out


async def poll_once() -> dict:
    sources = build_sources()
    new_total = 0
    errors: list[str] = []
    async with session_factory()() as db:
        rows = (
            await db.execute(
                select(SavedSearch, User)
                .join(User, SavedSearch.user_id == User.id)
                .where(SavedSearch.enabled == True, User.pipeline_enabled == 1)  # noqa: E712
            )
        ).all()
        async with httpx.AsyncClient(timeout=30) as client:
            for search, user in rows:
                params = SavedSearchParams(
                    keywords=search.keywords, insee=search.insee,
                    radius_km=search.radius_km, contract_type=search.contract_type,
                )
                for source in sources:
                    try:
                        postings = await source.fetch(params, client)
                        new_total += await ingest(db, user.id, postings)
                    except Exception as exc:  # noqa: BLE001 — reported, poll continues
                        log.warning("source %s failed: %s", source.name, exc)
                        errors.append(str(exc))
        await db.commit()
    return {"new": new_total, "errors": errors}


async def poll_loop() -> None:
    interval = max(5, get_settings().poll_interval_minutes) * 60
    while True:
        try:
            result = await poll_once()
            log.info("poll: %s new, %s errors", result["new"], len(result["errors"]))
        except Exception:  # pragma: no cover — loop must survive anything
            log.exception("poll loop iteration failed")
        await asyncio.sleep(interval)


@internal_router.post("/poll")
async def internal_poll(request: Request) -> dict:
    token = get_settings().internal_token
    if not token or request.headers.get("X-Internal-Token") != token:
        raise HTTPException(status_code=403, detail="Forbidden.")
    return await poll_once()
