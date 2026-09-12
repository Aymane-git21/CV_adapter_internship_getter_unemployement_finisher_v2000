"""Overboard mode end to end on the offline provider. Studio generation lands
a 100% keyword match (the deterministic backstop covers whatever the model
missed), truthful levels never get the backstop, and the auto-apply pipeline,
which can send documents to employers, never runs overboard."""
import asyncio

import pytest
from sqlalchemy import select

from backend.app.ai.fake import FakeProvider
from backend.app.db import session_factory
from backend.app.models import Job, User
from backend.app.pipeline_ingest import ingest
from backend.app.schemas import JobAnalysis, JobPostingIn, Keyword

from .conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email

# The offline tailor lists only the first 8 keywords in its "Key match" group,
# and the sample CV evidences none of the last four: those are the ones the
# backstop has to add.
_KEYWORDS = [
    Keyword(term=t, weight=2)
    for t in ("Python", "Kubernetes", "Docker", "PyTorch", "Airflow", "GCP", "MLOps", "RAG",
              "Rust", "Terraform", "Kafka", "Scala")
]
_UNEVIDENCED = {"Rust", "Terraform", "Kafka", "Scala"}


@pytest.fixture()
def wide_analysis(monkeypatch):
    async def analyze(self, jd, cv_text, language):
        return JobAnalysis(job_title="ML Engineer", company="Lumina", keywords=_KEYWORDS, notes="n")

    monkeypatch.setattr(FakeProvider, "analyze", analyze)


async def _wait(client, job_id: str) -> dict:
    for _ in range(150):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["status"] in ("completed", "failed"):
            return snap
        await asyncio.sleep(0.2)
    raise AssertionError("job did not finish in time")


async def _cv_doc(client, snap: dict) -> dict:
    cv = next(d for d in snap["documents"] if d["kind"] == "cv")
    return (await client.get(f"/api/documents/{cv['id']}?include_svg=false")).json()


async def _studio_generate(client, intensity: str) -> tuple[str, dict]:
    r = await client.post(
        "/api/auth/register", json={"email": unique_email(), "password": "longpassword1"}
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "cv_text": SAMPLE_CV_TEXT, "language": "en",
              "template": "onyx", "rewrite_intensity": intensity},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["jobs"][0]
    snap = await _wait(client, job_id)
    assert snap["status"] == "completed", snap.get("error")
    return job_id, await _cv_doc(client, snap)


async def test_overboard_lands_every_keyword(client, wide_analysis):
    job_id, cv = await _studio_generate(client, "overboard")
    assert cv["score_before"] < 100
    assert cv["score_after"] == 100 and cv["keywords"]["missing"] == []
    listed = {item for group in cv["data"]["skills"] for item in group["items"]}
    assert _UNEVIDENCED <= listed, "the backstop lists what the model never wrote"

    async with session_factory()() as db:
        job = await db.get(Job, job_id)
        assert job.gen_params["intensity"] == "overboard", "a retry must re-run overboard"


async def test_truthful_levels_never_get_the_backstop(client, wide_analysis):
    for level in ("max_ats", "major"):
        _, cv = await _studio_generate(client, level)
        assert set(cv["keywords"]["missing"]) == _UNEVIDENCED, level
        assert cv["score_after"] == round(100 * 16 / 24), level


async def test_pipeline_never_runs_overboard(client, wide_analysis):
    """Pipeline documents can be sent to employers from the review queue, so
    the fabricating level stays studio-only: the pipeline downgrades it."""
    email = unique_email()
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    await client.post("/api/cvs", json={"name": "Master", "raw_text": SAMPLE_CV_TEXT})
    async with session_factory()() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.pipeline_enabled = 1
        await ingest(db, user.id, [
            JobPostingIn(source="ft", external_id="OB1", title="ML Engineer", company="Lumina",
                         description=SAMPLE_JD, apply_email="hr@lumina.example"),
        ])
        await db.commit()
    app_id = (await client.get("/api/pipeline")).json()["applications"][0]["id"]

    r = await client.post("/api/pipeline/generate", json={
        "application_ids": [app_id], "template": "onyx", "accent": "#0F62FE",
        "language": "en", "rewrite_intensity": "overboard",
    })
    assert r.status_code == 200, r.text
    job_id = r.json()["jobs"][0]
    snap = await _wait(client, job_id)
    assert snap["status"] == "completed", snap.get("error")

    async with session_factory()() as db:
        assert (await db.get(Job, job_id)).gen_params["intensity"] == "major"
    cv = await _cv_doc(client, snap)
    assert set(cv["keywords"]["missing"]) == _UNEVIDENCED
