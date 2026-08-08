"""Pipeline jobs get an answers document; studio jobs stay 3-doc."""
import asyncio

from sqlalchemy import select

from backend.app.db import session_factory
from backend.app.models import Document, Job, User
from backend.app.schemas import FactsProfile
from backend.tests.conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email


async def _register_and_generate(client):
    email = unique_email()
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    body = {
        "job_descriptions": [SAMPLE_JD], "cv_text": SAMPLE_CV_TEXT, "language": "en",
        "template": "onyx", "accent": "#0F62FE", "show_photo": False,
    }
    r = await client.post("/api/generate", json=body)
    assert r.status_code == 200, r.text
    return email, r.json()["jobs"][0]


async def _wait_done(job_id, timeout_s=30):
    for _ in range(timeout_s * 10):
        async with session_factory()() as db:
            job = await db.get(Job, job_id)
            if job.status in ("completed", "failed"):
                return job.status
        await asyncio.sleep(0.1)
    raise TimeoutError


async def test_studio_job_still_three_documents(client):
    _, job_id = await _register_and_generate(client)
    assert await _wait_done(job_id) == "completed"
    async with session_factory()() as db:
        kinds = {
            d.kind for d in (await db.execute(select(Document).where(Document.job_id == job_id))).scalars()
        }
    assert kinds == {"cv", "letter", "message"}


async def test_pipeline_job_gets_answers_document(client):
    email, job_id = await _register_and_generate(client)
    assert await _wait_done(job_id) == "completed"
    # Simulate a pipeline-originated job: set posting_id in gen_params and user facts,
    # then re-run the pipeline via the retry endpoint (which replays gen_params).
    # /retry only accepts jobs in "failed" status (see test_api.py::test_retry_failed_job,
    # a completed job gets a pinned 409) so force that first.
    async with session_factory()() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.facts = FactsProfile(work_permit="EU citizen").model_dump()
        job = await db.get(Job, job_id)
        job.gen_params = {**(job.gen_params or {}), "posting_id": 42}
        job.status = "failed"
        await db.commit()
    r = await client.post(f"/api/jobs/{job_id}/retry")
    assert r.status_code == 200
    new_id = r.json()["id"]
    assert await _wait_done(new_id) == "completed"
    async with session_factory()() as db:
        docs = (await db.execute(select(Document).where(Document.job_id == new_id))).scalars().all()
    kinds = {d.kind for d in docs}
    assert kinds == {"cv", "letter", "message", "answers"}
    answers = next(d for d in docs if d.kind == "answers")
    items = answers.data["items"]
    origins = {i["origin"] for i in items}
    assert "facts" in origins and "generated" in origins
    facts_items = [i for i in items if i["origin"] == "facts"]
    assert facts_items[0]["answer"] == "EU citizen"
    # Ordering contract: fixed facts are merged BEFORE generated items. A set-based
    # origin check alone would still pass if the concatenation were reversed.
    first_generated = next(i for i, item in enumerate(items) if item["origin"] == "generated")
    assert all(item["origin"] == "facts" for item in items[:first_generated])
    assert items[0]["origin"] == "facts"
