"""Stripe billing: checkout, portal, and webhook plan transitions.

Stripe network calls are monkeypatched; webhook payloads are signed with the
real HMAC scheme so the signature-verification path is exercised for real.
"""
import hashlib
import hmac
import json
import time
import uuid

import stripe

from .conftest import unique_email
from .test_api import _register

WEBHOOK_SECRET = "whsec_testsecret"  # pinned in conftest


def _sign(payload: bytes) -> str:
    ts = int(time.time())
    mac = hmac.new(WEBHOOK_SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256)
    return f"t={ts},v1={mac.hexdigest()}"


async def _post_event(client, event: dict):
    payload = json.dumps({"object": "event", **event}).encode()
    return await client.post(
        "/api/billing/webhook",
        content=payload,
        headers={"stripe-signature": _sign(payload), "content-type": "application/json"},
    )


def _mock_checkout(monkeypatch, created_customers: list):
    """Customer ids must be unique across tests: the DB file is shared, and the
    webhook handler looks users up by stripe_customer_id."""

    def fake_customer_create(**kwargs):
        kwargs["id"] = f"cus_{uuid.uuid4().hex[:10]}"
        created_customers.append(kwargs)
        return {"id": kwargs["id"]}

    def fake_session_create(**kwargs):
        return {"url": "https://checkout.stripe.com/c/pay/cs_test_123", "sess": kwargs}

    monkeypatch.setattr(stripe.Customer, "create", staticmethod(fake_customer_create))
    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(fake_session_create))


async def test_checkout_unknown_plan(client):
    await _register(client)
    r = await client.post("/api/billing/checkout", json={"plan": "platinum"})
    assert r.status_code == 422


async def test_checkout_requires_auth(client):
    r = await client.post("/api/billing/checkout", json={"plan": "plus"})
    assert r.status_code == 401


async def test_checkout_creates_customer_once(client, monkeypatch):
    created = []
    _mock_checkout(monkeypatch, created)
    email = unique_email()
    await _register(client, email=email)

    r = await client.post("/api/billing/checkout", json={"plan": "plus"})
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("https://checkout.stripe.com/")
    assert len(created) == 1 and created[0]["email"] == email

    # Second checkout reuses the persisted stripe_customer_id.
    r = await client.post("/api/billing/checkout", json={"plan": "pro"})
    assert r.status_code == 200
    assert len(created) == 1


async def test_portal_without_billing_profile(client):
    await _register(client)
    r = await client.post("/api/billing/portal")
    assert r.status_code == 422


async def test_webhook_rejects_bad_signature(client):
    r = await client.post(
        "/api/billing/webhook",
        content=b'{"type": "checkout.session.completed"}',
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert r.status_code == 400


async def _me_plan(client) -> str:
    r = await client.get("/api/auth/me")
    assert r.status_code == 200
    return r.json()["plan"]


async def test_webhook_upgrade_and_cancel_cycle(client, monkeypatch):
    created = []
    _mock_checkout(monkeypatch, created)
    await _register(client)
    r = await client.post("/api/billing/checkout", json={"plan": "pro"})
    assert r.status_code == 200
    customer_id = created[0]["id"]

    r = await _post_event(
        client,
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": customer_id,
                    "subscription": "sub_test_1",
                    "metadata": {"user_id": "1", "plan": "pro"},
                }
            },
        },
    )
    assert r.status_code == 200 and r.json() == {"received": True}
    assert await _me_plan(client) == "pro"

    # Subscription canceled -> back to free.
    r = await _post_event(
        client,
        {
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": customer_id, "status": "canceled", "metadata": {}}},
        },
    )
    assert r.status_code == 200
    assert await _me_plan(client) == "free"


async def test_webhook_subscription_updated_active(client, monkeypatch):
    created = []
    _mock_checkout(monkeypatch, created)
    await _register(client)
    await client.post("/api/billing/checkout", json={"plan": "plus"})
    customer_id = created[0]["id"]

    r = await _post_event(
        client,
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {"customer": customer_id, "status": "active", "metadata": {"plan": "plus"}}
            },
        },
    )
    assert r.status_code == 200
    assert await _me_plan(client) == "plus"

    # Payment failure ends the subscription -> downgrade.
    r = await _post_event(
        client,
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {"customer": customer_id, "status": "unpaid", "metadata": {"plan": "plus"}}
            },
        },
    )
    assert r.status_code == 200
    assert await _me_plan(client) == "free"
