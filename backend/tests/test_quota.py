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
