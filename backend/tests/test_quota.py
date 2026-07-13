"""Server-side quota enforcement."""
from .conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email
from .test_api import _register, _wait_job


async def test_free_plan_template_lock(client):
    await _register(client)
    r = await client.post("/api/cvs", json={"name": "M", "raw_text": SAMPLE_CV_TEXT})
    cv_id = r.json()["id"]
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "master_cv_id": cv_id, "template": "compact"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "template_locked"


async def test_free_plan_parallel_lock(client):
    await _register(client)
    r = await client.post("/api/cvs", json={"name": "M", "raw_text": SAMPLE_CV_TEXT})
    cv_id = r.json()["id"]
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD, SAMPLE_JD + " bis"], "master_cv_id": cv_id,
              "template": "onyx"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "parallel_limit"


async def test_free_plan_daily_limit(client):
    await _register(client)
    r = await client.post("/api/cvs", json={"name": "M", "raw_text": SAMPLE_CV_TEXT})
    cv_id = r.json()["id"]

    for i in range(3):
        r = await client.post(
            "/api/generate",
            json={"job_descriptions": [SAMPLE_JD + f" variant {i}"], "master_cv_id": cv_id,
                  "template": "onyx"},
        )
        assert r.status_code == 200, r.text
        await _wait_job(client, r.json()["jobs"][0])

    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD + " final"], "master_cv_id": cv_id, "template": "onyx"},
    )
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "daily_limit"


async def test_unique_emails_isolated():
    # Sanity: helper produces unique addresses (used across tests sharing one DB).
    assert unique_email() != unique_email()


class _ExplodingProvider:
    """Provider whose first pipeline call fails like a Gemini outage."""

    async def analyze(self, jd, cv_text, language):
        from backend.app.ai.base import AIError

        raise AIError("The AI service is at capacity right now. Try again shortly.")


async def test_failed_job_refunds_user_quota(client, monkeypatch):
    """A failed generation must not eat the caller's daily allowance."""
    monkeypatch.setattr("backend.app.jobs.get_provider", lambda byok_key=None: _ExplodingProvider())
    await _register(client)
    r = await client.post("/api/cvs", json={"name": "M", "raw_text": SAMPLE_CV_TEXT})
    cv_id = r.json()["id"]

    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "master_cv_id": cv_id, "template": "onyx"},
    )
    assert r.status_code == 200, r.text
    snap = await _wait_job(client, r.json()["jobs"][0])
    assert snap["status"] == "failed"

    me = (await client.get("/api/auth/me")).json()
    assert me["quota"]["used_today"] == 0


async def test_failed_job_refunds_guest_quota(client, monkeypatch):
    """Guests get one generation a day; a failed attempt must not consume it."""
    # Guest usage is keyed by client IP, which every test shares: start clean.
    from sqlalchemy import delete

    from backend.app.db import session_factory
    from backend.app.models import GuestUsage

    async with session_factory()() as db:
        await db.execute(delete(GuestUsage))
        await db.commit()

    monkeypatch.setattr("backend.app.jobs.get_provider", lambda byok_key=None: _ExplodingProvider())
    body = {"job_descriptions": [SAMPLE_JD], "cv_text": SAMPLE_CV_TEXT, "template": "onyx"}

    r = await client.post("/api/generate", json=body)
    assert r.status_code == 200, r.text
    snap = await _wait_job(client, r.json()["jobs"][0])
    assert snap["status"] == "failed"

    # The refund means the guest can try again instead of hitting guest_limit.
    r = await client.post("/api/generate", json=body)
    assert r.status_code == 200, r.text
    await _wait_job(client, r.json()["jobs"][0])
