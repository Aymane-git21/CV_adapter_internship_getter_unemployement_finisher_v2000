"""End-to-end review queue on the fake AI: ingest -> generate -> approve -> send (.eml)."""
import asyncio

from sqlalchemy import select

from backend.app.db import session_factory
from backend.app.models import User
from backend.app.pipeline_ingest import ingest
from backend.app.schemas import JobPostingIn
from backend.tests.conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email


async def _setup_user(client, pipeline=True):
    email = unique_email()
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    await client.post("/api/cvs", json={"name": "Master", "raw_text": SAMPLE_CV_TEXT})
    async with session_factory()() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.pipeline_enabled = 1 if pipeline else 0
        await ingest(db, user.id, [
            JobPostingIn(source="ft", external_id="R1", title="ML Engineer", company="Lumina",
                         description=SAMPLE_JD, apply_email="hr@lumina.example"),
        ])
        await db.commit()
        return email, user.id


async def _wait_jobs(client, job_ids, timeout_s=30):
    for _ in range(timeout_s * 10):
        snaps = [await client.get(f"/api/jobs/{j}") for j in job_ids]
        if all(s.json()["status"] in ("completed", "failed") for s in snaps):
            return [s.json()["status"] for s in snaps]
        await asyncio.sleep(0.1)
    raise TimeoutError


async def test_full_queue_flow_with_eml(client, tmp_path, monkeypatch):
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "eml_out_dir", str(tmp_path), raising=False)

    email, uid = await _setup_user(client)
    board = (await client.get("/api/pipeline")).json()["applications"]
    assert len(board) == 1 and board[0]["status"] == "inbox"
    app_id = board[0]["id"]
    assert board[0]["posting"]["apply_email"] == "hr@lumina.example"

    r = await client.post("/api/pipeline/generate", json={
        "application_ids": [app_id], "template": "onyx", "accent": "#0F62FE",
        "language": "fr", "rewrite_intensity": "major",
    })
    assert r.status_code == 200, r.text
    assert await _wait_jobs(client, r.json()["jobs"]) == ["completed"]

    board = (await client.get("/api/pipeline")).json()["applications"]
    assert board[0]["status"] == "generated" and board[0]["job_id"]

    assert (await client.post(f"/api/pipeline/{app_id}/approve")).status_code == 200
    r = await client.post(f"/api/pipeline/{app_id}/send", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sent_via"] == "eml" and body["status"] == "sent"
    assert list(tmp_path.glob("*.eml")), "eml file written"


async def test_send_requires_approved_state(client, tmp_path, monkeypatch):
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "eml_out_dir", str(tmp_path), raising=False)
    _, uid = await _setup_user(client)
    app_id = (await client.get("/api/pipeline")).json()["applications"][0]["id"]
    r = await client.post(f"/api/pipeline/{app_id}/send", json={})
    assert r.status_code == 409


async def test_pipeline_flag_gates_access(client):
    await _setup_user(client, pipeline=False)
    assert (await client.get("/api/pipeline")).status_code == 403


async def test_send_cap_enforced(client, tmp_path, monkeypatch):
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "eml_out_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(get_settings(), "send_cap_daily", 0, raising=False)
    _, uid = await _setup_user(client)
    app_id = (await client.get("/api/pipeline")).json()["applications"][0]["id"]
    r = await client.post("/api/pipeline/generate", json={
        "application_ids": [app_id], "template": "onyx", "accent": "#0F62FE",
        "language": "fr", "rewrite_intensity": "major",
    })
    await _wait_jobs(client, r.json()["jobs"])
    await client.post(f"/api/pipeline/{app_id}/approve")
    r = await client.post(f"/api/pipeline/{app_id}/send", json={})
    assert r.status_code == 429
