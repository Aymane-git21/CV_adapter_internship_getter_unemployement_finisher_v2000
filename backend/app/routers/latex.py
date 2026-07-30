"""LaTeX compiler session control.

Warmth model: enabling the LaTeX compiler warms the latexc Cloud Run service
(min-instances 1) and it STAYS warm until turned off manually
(`python ops/latexc.py off`) or by the idle reaper (LATEXC_IDLE_OFF_MINUTES,
0 disables it). "End session" clears one document's remote compile cache and
never scales the service down."""
import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..db import get_db, session_factory
from ..models import Document, LatexActivity, User
from ..quota import plan_for
from ..security import require_user
from ..texsvc import client as latexc_client

router = APIRouter(prefix="/api/latex", tags=["latex"])
log = logging.getLogger("cvglowup.latex")

_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)


def admin_service_url(s: Settings) -> str:
    """Cloud Run Admin API v2 resource URL for the latexc service (pure, tested)."""
    return (
        f"https://run.googleapis.com/v2/projects/{s.gcp_project}"
        f"/locations/{s.latexc_region}/services/{s.latexc_service}"
    )


def min_instances_patch() -> dict:
    return {"updateMask": "scaling.minInstanceCount"}


async def _metadata_token() -> str | None:
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            resp = await c.get(_METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
            resp.raise_for_status()
            return resp.json().get("access_token")
    except (httpx.HTTPError, ValueError):
        log.warning("metadata token unavailable (not on GCP?)")
        return None


async def set_min_instances(n: int) -> bool:
    s = get_settings()
    token = await _metadata_token()
    if token is None:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.patch(
                admin_service_url(s),
                params=min_instances_patch(),
                headers={"Authorization": f"Bearer {token}"},
                json={"scaling": {"minInstanceCount": n}},
            )
            resp.raise_for_status()
        log.info("latexc min-instances -> %s", n)
        return True
    except httpx.HTTPError as exc:
        log.error("latexc scaling PATCH failed: %s", exc)
        return False


def _require_latex(user: User) -> None:
    if not get_settings().latex_enabled:
        raise HTTPException(status_code=404, detail="LaTeX compiler is not configured.")
    if not plan_for(user).latex:
        raise HTTPException(
            status_code=403,
            detail={"code": "latex_locked", "message": "The LaTeX compiler requires a higher plan."},
        )


@router.post("/warmup")
async def warmup(user: Annotated[User, Depends(require_user)]):
    _require_latex(user)
    s = get_settings()
    if await latexc_client.service_status():
        return {"warm": True, "starting": False}
    starting = False
    if s.is_prod:
        starting = await set_min_instances(1)
    return {"warm": False, "starting": starting}


@router.get("/status")
async def latex_status(user: Annotated[User, Depends(require_user)]):
    s = get_settings()
    if not s.latex_enabled:
        return {"enabled": False, "warm": False}
    return {"enabled": True, "warm": await latexc_client.service_status()}


@router.post("/session/{doc_id}/end", status_code=204)
async def end_session(
    doc_id: str,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_latex(user)
    doc = await db.get(Document, doc_id)
    if doc is None or (doc.user_id is not None and doc.user_id != user.id):
        raise HTTPException(status_code=404, detail="Document not found.")
    await latexc_client.clear_project(doc_id)


def idle_exceeded(last_compile_at: datetime, now: datetime, idle_off_minutes: int) -> bool:
    """Pure reaper decision (unit-tested)."""
    if last_compile_at.tzinfo is None:
        last_compile_at = last_compile_at.replace(tzinfo=UTC)
    return (now - last_compile_at).total_seconds() > idle_off_minutes * 60


async def idle_reaper() -> None:
    """Background task (prod only): scale the warm service to zero after
    LATEXC_IDLE_OFF_MINUTES without a LaTeX compile. The billing backstop for
    a forgotten warm instance; set the env to 0 for strictly-manual off."""
    while True:
        await asyncio.sleep(600)
        try:
            s = get_settings()
            if not (s.latex_enabled and s.is_prod and s.latexc_idle_off_minutes > 0):
                continue
            async with session_factory()() as db:
                row = await db.get(LatexActivity, 1)
            if row is None:
                continue
            if not idle_exceeded(row.last_compile_at, datetime.now(UTC), s.latexc_idle_off_minutes):
                continue
            if await latexc_client.service_status():
                if await set_min_instances(0):
                    log.info("idle reaper scaled latexc to zero")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("idle reaper iteration failed")
