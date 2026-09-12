"""The profile page edits the master CV: the data every tailored CV is built
from. Pinned here: a save changes only what it sends, cleans what it stores,
clamps names, stays owner-scoped, and the next generation reads the edit."""
import asyncio

from backend.app.ai.fake import FakeProvider
from backend.app.routers.cvs import clean_cv
from backend.app.schemas import CVData, JobAnalysis, Keyword

from .conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email


async def _register(client):
    r = await client.post(
        "/api/auth/register", json={"email": unique_email(), "password": "longpassword1"}
    )
    assert r.status_code == 200, r.text


async def _create(client, name="Main") -> dict:
    r = await client.post("/api/cvs", json={"name": name, "raw_text": SAMPLE_CV_TEXT})
    assert r.status_code == 200, r.text
    return r.json()


def test_clean_cv_trims_and_drops_blank_entries():
    cv = CVData.model_validate({
        "full_name": "  Alex  ",
        "experience": [
            {"title": "Engineer", "company": "Acme", "bullets": ["  Built X  ", "", "   "]},
            {"title": "", "company": "", "bullets": [""]},
        ],
        "education": [{"degree": "", "school": "", "details": []}],
        "skills": [{"category": "Tools", "items": ["Docker", " ", ""]}, {"category": "", "items": []}],
        "interests": ["", "chess", "  "],
    })
    out = clean_cv(cv)
    assert out.full_name == "Alex"
    assert [e.title for e in out.experience] == ["Engineer"]
    assert out.experience[0].bullets == ["Built X"]
    assert out.education == []
    assert [(g.category, g.items) for g in out.skills] == [("Tools", ["Docker"])]
    assert out.interests == ["chess"]
    assert out.contacts.email == "", "records like contacts are trimmed, never dropped"


async def test_data_only_save_keeps_the_name(client):
    await _register(client)
    cv = await _create(client, "Data science")
    data = {**cv["data"], "headline": "Senior ML Engineer"}
    r = await client.put(f"/api/cvs/{cv['id']}", json={"data": data})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Data science", "a data-only save renamed the CV"
    assert r.json()["data"]["headline"] == "Senior ML Engineer"


async def test_save_cleans_data_and_clamps_the_name(client):
    await _register(client)
    cv = await _create(client)
    blank_role = {"title": "", "company": "", "location": "", "start": "", "end": "", "bullets": [""]}
    data = {**cv["data"], "interests": ["chess", "", "  "],
            "experience": [*cv["data"]["experience"], blank_role]}
    r = await client.put(f"/api/cvs/{cv['id']}", json={"name": "x" * 300, "data": data})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["name"]) == 120
    assert body["data"]["interests"] == ["chess"]
    assert len(body["data"]["experience"]) == len(cv["data"]["experience"])

    listed = next(c for c in (await client.get("/api/cvs")).json() if c["id"] == cv["id"])
    assert listed["data"] == body["data"], "the list serves exactly what was saved"


async def test_save_is_owner_scoped(client):
    await _register(client)
    cv = await _create(client)
    client.cookies.clear()
    await _register(client)
    r = await client.put(f"/api/cvs/{cv['id']}", json={"data": cv["data"]})
    assert r.status_code == 404


async def test_next_generation_reads_the_edited_master_cv(client, monkeypatch):
    async def analyze(self, jd, cv_text, language):
        return JobAnalysis(job_title="ML Engineer", keywords=[Keyword(term="Rust", weight=1)], notes="n")

    monkeypatch.setattr(FakeProvider, "analyze", analyze)
    await _register(client)
    cv = await _create(client)
    data = {**cv["data"], "skills": [*cv["data"]["skills"], {"category": "Systems", "items": ["Rust"]}]}
    assert (await client.put(f"/api/cvs/{cv['id']}", json={"data": data})).status_code == 200

    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "master_cv_id": cv["id"], "language": "en",
              "template": "onyx"},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["jobs"][0]
    for _ in range(150):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.2)
    assert snap["status"] == "completed", snap.get("error")
    cv_doc = next(d for d in snap["documents"] if d["kind"] == "cv")
    assert cv_doc["score_before"] == 100, "generation must start from the edited master CV"
