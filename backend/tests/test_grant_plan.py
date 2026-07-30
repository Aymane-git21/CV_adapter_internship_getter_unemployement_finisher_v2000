"""Gate tests for the grant_plan admin script (backend/scripts/grant_plan.py).

Runs against the test sqlite DB pinned in conftest — never touches production.
"""
import pytest
from sqlalchemy import select

from backend.app.db import dispose_db, init_db, session_factory
from backend.app.models import User
from backend.app.security import verify_password
from backend.scripts.grant_plan import apply, generate_password


async def _fetch(email: str) -> User | None:
    async with session_factory()() as db:
        return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


@pytest.fixture
async def db():
    await init_db()
    yield
    await dispose_db()


async def test_creates_missing_user_on_plan(db):
    email = "grant-new@example.com"
    results = await apply([email], "pro", {email: "s3cret-pw"})

    assert results == [(email, "created", "pro")]
    user = await _fetch(email)
    assert user is not None
    assert user.plan == "pro"
    assert verify_password("s3cret-pw", user.password_hash)


async def test_upgrade_keeps_existing_password_by_default(db):
    email = "grant-existing@example.com"
    await apply([email], "free", {email: "old-pw"})
    results = await apply([email], "pro", {email: "new-pw"})  # generated pw, not explicit

    assert results == [(email, "updated", "pro")]
    user = await _fetch(email)
    assert user.plan == "pro"
    assert verify_password("old-pw", user.password_hash), "upgrade must not reset the login"
    assert not verify_password("new-pw", user.password_hash)


async def test_upgrade_resets_password_when_explicitly_asked(db):
    email = "grant-reset@example.com"
    await apply([email], "free", {email: "old-pw"})
    results = await apply([email], "pro", {email: "new-pw"}, set_password=True)

    assert results == [(email, "updated", "pro")]
    user = await _fetch(email)
    assert verify_password("new-pw", user.password_hash)
    assert not verify_password("old-pw", user.password_hash)


async def test_email_is_normalised_to_lowercase(db):
    results = await apply(["Grant-Case@Example.COM"], "pro", {"grant-case@example.com": "pw"})

    assert results[0][0] == "grant-case@example.com"
    assert await _fetch("grant-case@example.com") is not None


async def test_generated_password_is_long_and_unambiguous():
    pw = generate_password()
    assert len(pw) == 16
    assert not set(pw) & set("l1I0O")
    assert generate_password() != generate_password()
