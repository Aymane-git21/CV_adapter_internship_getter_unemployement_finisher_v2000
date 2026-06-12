"""Stripe billing: Checkout, customer portal, webhooks. Fully env-gated —
without Stripe keys the endpoints respond 501 and the frontend hides paid CTAs."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import User
from ..security import require_user

router = APIRouter(prefix="/api/billing", tags=["billing"])
log = logging.getLogger(__name__)


class CheckoutIn(BaseModel):
    plan: str  # plus | pro


def _stripe():
    settings = get_settings()
    if not settings.billing_enabled:
        raise HTTPException(status_code=501, detail="Billing is not configured on this deployment.")
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


def _base_url(request: Request) -> str:
    settings = get_settings()
    return settings.public_base_url or str(request.base_url).rstrip("/")


@router.post("/checkout")
async def create_checkout(
    body: CheckoutIn,
    request: Request,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stripe = _stripe()
    settings = get_settings()
    price = {"plus": settings.stripe_price_plus, "pro": settings.stripe_price_pro}.get(body.plan)
    if not price:
        raise HTTPException(status_code=422, detail="Unknown plan.")

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
        user.stripe_customer_id = customer["id"]
        await db.commit()

    base = _base_url(request)
    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price, "quantity": 1}],
        success_url=f"{base}/pricing?upgraded=1",
        cancel_url=f"{base}/pricing?canceled=1",
        metadata={"user_id": str(user.id), "plan": body.plan},
        subscription_data={"metadata": {"user_id": str(user.id), "plan": body.plan}},
    )
    return {"url": session["url"]}


@router.post("/portal")
async def customer_portal(
    request: Request,
    user: Annotated[User, Depends(require_user)],
):
    stripe = _stripe()
    if not user.stripe_customer_id:
        raise HTTPException(status_code=422, detail="No billing profile yet.")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id, return_url=f"{_base_url(request)}/settings"
    )
    return {"url": session["url"]}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    stripe = _stripe()
    settings = get_settings()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.") from exc

    etype = event["type"]
    obj = event["data"]["object"]

    async def _user_for_customer(customer_id: str) -> User | None:
        return (
            await db.execute(select(User).where(User.stripe_customer_id == customer_id))
        ).scalar_one_or_none()

    if etype == "checkout.session.completed":
        user = await _user_for_customer(obj.get("customer", ""))
        plan = (obj.get("metadata") or {}).get("plan")
        if user and plan in ("plus", "pro"):
            user.plan = plan
            user.stripe_subscription_id = obj.get("subscription")
            await db.commit()
            log.info("user %s upgraded to %s", user.id, plan)
    elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
        user = await _user_for_customer(obj.get("customer", ""))
        if user:
            status = obj.get("status")
            plan = (obj.get("metadata") or {}).get("plan", "plus")
            if etype == "customer.subscription.deleted" or status in ("canceled", "unpaid", "incomplete_expired"):
                user.plan = "free"
                user.stripe_subscription_id = None
            elif status in ("active", "trialing"):
                user.plan = plan if plan in ("plus", "pro") else "plus"
            await db.commit()
    return {"received": True}
