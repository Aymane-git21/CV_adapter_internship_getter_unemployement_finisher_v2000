"""Create or upgrade accounts on a given plan, locally or against production.

Deterministic admin tool: same inputs -> same DB state. Never prints the
database URL. Passwords are generated here (or supplied) and printed once so
they can be handed to the account owner.

    # local sqlite (uses .env DATABASE_URL)
    .venv\\Scripts\\python -m backend.scripts.grant_plan a@x.com b@x.com

    # production (pulls DATABASE_URL from Secret Manager, never echoes it)
    .venv\\Scripts\\python -m backend.scripts.grant_plan --prod --plan pro a@x.com

    # fixed password instead of a generated one
    .venv\\Scripts\\python -m backend.scripts.grant_plan --password 'hunter2' a@x.com
"""
from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import subprocess
import sys

PLANS = ("free", "plus", "pro")
GCP_PROJECT = os.environ.get("GCP_PROJECT_ID", "project-60fad876-6da7-41f3-bfd")
SECRET_NAME = "DATABASE_URL"

# Ambiguous glyphs removed: humans retype these.
_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_password(length: int = 16) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def fetch_prod_database_url() -> str:
    """Read DATABASE_URL from Secret Manager into memory only."""
    proc = subprocess.run(
        [
            "gcloud", "secrets", "versions", "access", "latest",
            f"--secret={SECRET_NAME}", f"--project={GCP_PROJECT}",
        ],
        capture_output=True,
        text=True,
        shell=os.name == "nt",
    )
    if proc.returncode != 0:
        # stderr may not contain the secret, but stay conservative.
        raise SystemExit(f"failed to read {SECRET_NAME} from Secret Manager (exit {proc.returncode})")
    url = proc.stdout.strip()
    if not url:
        raise SystemExit(f"{SECRET_NAME} secret is empty")
    return url


async def apply(
    emails: list[str], plan: str, passwords: dict[str, str], set_password: bool = False
) -> list[tuple[str, str, str]]:
    """Upsert each email at `plan`. New accounts always get their password set;
    existing accounts keep theirs unless set_password (an explicit --password)
    is given — upgrading a plan must not silently reset a login."""
    from sqlalchemy import select

    from backend.app.db import dispose_db, init_db, session_factory
    from backend.app.models import User
    from backend.app.security import hash_password

    await init_db()
    results: list[tuple[str, str, str]] = []
    async with session_factory()() as db:
        for email in emails:
            email = email.strip().lower()
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            action = "updated"
            if user is None:
                user = User(email=email)
                db.add(user)
                action = "created"
            if action == "created" or set_password:
                user.password_hash = hash_password(passwords[email])
            user.plan = plan
            results.append((email, action, plan))
        await db.commit()
    await dispose_db()
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("emails", nargs="+")
    ap.add_argument("--plan", default="pro", choices=PLANS)
    ap.add_argument("--prod", action="store_true", help="target the deployed database")
    ap.add_argument("--password", default=None, help="use this password for every account")
    args = ap.parse_args(argv)

    if args.prod:
        # Set before backend.app.config is imported so Settings picks it up.
        os.environ["DATABASE_URL"] = fetch_prod_database_url()

    emails = [e.strip().lower() for e in args.emails]
    passwords = {e: (args.password or generate_password()) for e in emails}

    results = asyncio.run(apply(emails, args.plan, passwords, set_password=args.password is not None))

    target = "PRODUCTION" if args.prod else "local"
    print(f"target: {target}")
    for email, action, plan in results:
        pw = passwords[email] if (action == "created" or args.password is not None) else "(kept)"
        print(f"  {action:<8} {email:<32} plan={plan}  password={pw}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
