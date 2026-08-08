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
        # Read every value the inner loop needs out of the ORM rows now, before
        # any commit/rollback: Session.rollback() unconditionally expires every
        # object loaded in the transaction (not just the ones touched in the
        # failed unit of work — this is separate from expire_on_commit, which
        # only governs commit()), and touching an expired attribute on an
        # AsyncSession outside of an awaited call raises MissingGreenlet. Since
        # the loop below commits/rolls back per (search, source) pair, `search`
        # and `user` must never be read again past this point.
        jobs = [
            (
                user.id,
                SavedSearchParams(
                    keywords=search.keywords, insee=search.insee,
                    radius_km=search.radius_km, contract_type=search.contract_type,
                ),
            )
            for search, user in rows
        ]
        async with httpx.AsyncClient(timeout=30) as client:
            for user_id, params in jobs:
                for source in sources:
                    try:
                        postings = await source.fetch(params, client)
                        new_total += await ingest(db, user_id, postings)
                        # Commit per (search, source) pair rather than once at the
                        # end: a failed flush leaves the session in
                        # PendingRollbackError state, so the rollback below
                        # restores it and later sources still land; per-pair
                        # commits also mean a later error never discards an
                        # earlier source's already-ingested postings.
                        await db.commit()
                    except Exception as exc:  # noqa: BLE001 — reported, poll continues
                        log.warning("source %s failed: %s", source.name, exc)
                        errors.append(f"{source.name}: {exc}")
                        await db.rollback()
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
