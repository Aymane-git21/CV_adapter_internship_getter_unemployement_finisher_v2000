"""Idempotent Stripe account setup for CV Glowup.

Creates (or finds) the subscription Products/Prices matching backend/app/quota.py
and the production webhook endpoint, then prints the env lines to paste into
.env / the Cloud Run env. Safe to re-run; re-run once more with live keys when
switching out of test mode.

Usage:
    python ops/stripe_setup.py                     # uses STRIPE_SECRET_KEY from env or .env
    python ops/stripe_setup.py --rotate-webhook    # delete + recreate the webhook endpoint
                                                   # (the signing secret is only shown at creation)
"""
import argparse
import os
import sys
from pathlib import Path

import stripe

REPO_ROOT = Path(__file__).resolve().parents[1]
WEBHOOK_URL = "https://cvglowup.com/api/billing/webhook"
WEBHOOK_EVENTS = [
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
]

# lookup_key -> (product name, unit_amount in cents, env var)
PRICES = {
    "cvg_plus_monthly": ("CV Glowup Plus", 500, "STRIPE_PRICE_PLUS"),
    "cvg_pro_monthly": ("CV Glowup Pro", 1200, "STRIPE_PRICE_PRO"),
}


def _load_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("STRIPE_SECRET_KEY="):
                    key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("STRIPE_SECRET_KEY not set (env or .env).")
    return key


def ensure_price(lookup_key: str, product_name: str, unit_amount: int) -> str:
    found = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
    if found.data:
        price = found.data[0]
        if price.unit_amount != unit_amount or price.currency != "eur":
            print(
                f"  WARNING: existing price {price.id} ({lookup_key}) is "
                f"{price.unit_amount} {price.currency}, expected {unit_amount} eur. "
                "Fix in the Stripe dashboard if intentional pricing changed.",
            )
        return price.id
    product = stripe.Product.create(name=product_name, metadata={"app": "cvglowup"})
    price = stripe.Price.create(
        product=product.id,
        currency="eur",
        unit_amount=unit_amount,
        recurring={"interval": "month"},
        lookup_key=lookup_key,
    )
    print(f"  created {product_name}: {price.id}")
    return price.id


def ensure_webhook(rotate: bool) -> str | None:
    """Returns the signing secret if (re)created, None if left untouched."""
    existing = [e for e in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter() if e.url == WEBHOOK_URL]
    if existing and not rotate:
        print(f"  webhook already exists ({existing[0].id}); secret only shown at creation.")
        print("  Re-run with --rotate-webhook if you need a fresh STRIPE_WEBHOOK_SECRET.")
        return None
    for e in existing:
        stripe.WebhookEndpoint.delete(e.id)
        print(f"  deleted old webhook {e.id}")
    endpoint = stripe.WebhookEndpoint.create(url=WEBHOOK_URL, enabled_events=WEBHOOK_EVENTS)
    print(f"  created webhook {endpoint.id} -> {WEBHOOK_URL}")
    return endpoint.secret


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rotate-webhook", action="store_true")
    args = parser.parse_args()

    stripe.api_key = _load_key()
    mode = "TEST" if stripe.api_key.startswith("sk_test_") else "LIVE"
    print(f"Stripe mode: {mode}")

    print("Prices:")
    env_lines: list[str] = []
    for lookup_key, (name, cents, env_var) in PRICES.items():
        price_id = ensure_price(lookup_key, name, cents)
        env_lines.append(f"{env_var}={price_id}")

    print("Webhook:")
    secret = ensure_webhook(args.rotate_webhook)
    if secret:
        env_lines.append(f"STRIPE_WEBHOOK_SECRET={secret}")

    print("\n--- env lines ---")
    for line in env_lines:
        print(line)


if __name__ == "__main__":
    main()
