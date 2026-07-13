"""Plan definitions and server-side quota enforcement."""
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import GuestUsage, Job, User

ALL_TEMPLATES = ["onyx", "classic", "compact"]


@dataclass(frozen=True)
class Plan:
    key: str
    label: str
    daily: int
    parallel: int
    templates: tuple[str, ...]
    price_eur: float


PLANS: dict[str, Plan] = {
    "guest": Plan("guest", "Guest", 1, 1, ("onyx",), 0),
    "free": Plan("free", "Free", 3, 1, ("onyx", "classic"), 0),
    "plus": Plan("plus", "Plus", 30, 3, tuple(ALL_TEMPLATES), 5.0),
    "pro": Plan("pro", "Pro", 1000, 10, tuple(ALL_TEMPLATES), 12.0),
}

# Bring-your-own-key: the user pays Gemini directly, so daily caps don't apply.
BYOK_PARALLEL = 3


def plan_for(user: User | None) -> Plan:
    if user is None:
        return PLANS["guest"]
    return PLANS.get(user.plan, PLANS["free"])


def _today():
    return datetime.now(UTC).date()


async def _running_jobs(db: AsyncSession, user_id: int | None, guest_hash: str | None) -> int:
    q = select(func.count(Job.id)).where(Job.status.in_(("queued", "running")))
    if user_id is not None:
        q = q.where(Job.user_id == user_id)
    else:
        # Guests are not tracked per-IP at the job level; cap is enforced per batch.
        return 0
    return (await db.execute(q)).scalar_one()


async def check_quota(
    db: AsyncSession,
    user: User | None,
    guest_hash: str | None,
    n_jobs: int,
    byok: bool,
    template: str,
) -> None:
    """Raise HTTPException(403/429) when the request exceeds the caller's plan."""
    plan = plan_for(user)

    if template not in (ALL_TEMPLATES if byok else list(plan.templates)):
        raise HTTPException(
            status_code=403,
            detail={"code": "template_locked", "message": f"Template '{template}' requires a higher plan."},
        )

    parallel_cap = BYOK_PARALLEL if byok else plan.parallel
    if n_jobs > parallel_cap:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "parallel_limit",
                "message": f"Your plan runs up to {parallel_cap} job descriptions at once (you sent {n_jobs}).",
            },
        )
    running = await _running_jobs(db, user.id if user else None, guest_hash)
    if running + n_jobs > parallel_cap:
        raise HTTPException(
            status_code=429,
            detail={"code": "busy", "message": "Previous generations are still running. Wait for them to finish."},
        )

    if byok:
        return  # their key, their bill — no daily cap

    today = _today()
    if user is not None:
        if user.gens_date != today:
            user.gens_date = today
            user.gens_today = 0
        if user.gens_today + n_jobs > plan.daily:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "daily_limit",
                    "message": f"Daily limit reached ({plan.daily}/day on {plan.label}). "
                    "Upgrade, come back tomorrow, or plug in your own Gemini API key for unlimited use.",
                },
            )
        user.gens_today += n_jobs
    else:
        assert guest_hash is not None
        row = (
            await db.execute(
                select(GuestUsage).where(GuestUsage.key_hash == guest_hash, GuestUsage.day == today)
            )
        ).scalar_one_or_none()
        if row is None:
            row = GuestUsage(key_hash=guest_hash, day=today, count=0)
            db.add(row)
        if row.count + n_jobs > PLANS["guest"].daily:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "guest_limit",
                    "message": "Free guest generation used up. Create a free account for more, "
                    "or add your own Gemini API key.",
                },
            )
        row.count += n_jobs


async def refund_one(db: AsyncSession, user_id: int | None, guest_hash: str | None) -> None:
    """Give back one generation charged by check_quota.

    Called when a job fails (AI outage, rate limit, render error): the caller
    got nothing, so the attempt must not count against their daily cap.
    """
    today = _today()
    if user_id is not None:
        user = await db.get(User, user_id)
        if user is not None and user.gens_date == today and user.gens_today > 0:
            user.gens_today -= 1
    elif guest_hash:
        row = (
            await db.execute(
                select(GuestUsage).where(GuestUsage.key_hash == guest_hash, GuestUsage.day == today)
            )
        ).scalar_one_or_none()
        if row is not None and row.count > 0:
            row.count -= 1


def quota_snapshot(user: User | None) -> dict:
    plan = plan_for(user)
    used = 0
    if user is not None and user.gens_date == _today():
        used = user.gens_today
    return {
        "plan": plan.key,
        "label": plan.label,
        "daily_limit": plan.daily,
        "used_today": used,
        "remaining_today": max(0, plan.daily - used),
        "parallel": plan.parallel,
        "templates": list(plan.templates),
    }
