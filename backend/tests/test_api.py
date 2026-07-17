"""End-to-end API flow against the offline provider and real Typst engine."""
import asyncio

from .conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email


async def _register(client, email=None):
    r = await client.post(
        "/api/auth/register", json={"email": email or unique_email(), "password": "longpassword1"}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _wait_job(client, job_id, max_wait=45.0):
    for _ in range(int(max_wait / 0.4)):
        r = await client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200
        snap = r.json()
        if snap["status"] in ("completed", "failed"):
            return snap
        await asyncio.sleep(0.4)
    raise AssertionError("job did not finish in time")


async def test_full_flow(client):
    me = await client.get("/api/auth/me")
    assert me.json()["authenticated"] is False

    user = await _register(client)
    assert user["plan"] == "free"

    # Save a master CV from pasted text (offline parser).
    r = await client.post("/api/cvs", json={"name": "Main", "raw_text": SAMPLE_CV_TEXT})
    assert r.status_code == 200, r.text
    cv_id = r.json()["id"]
    assert r.json()["is_default"] is True
    assert r.json()["data"]["full_name"].startswith("Alex")

    # Generate against one JD.
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "master_cv_id": cv_id, "language": "en",
              "template": "onyx", "accent": "#0F62FE"},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["jobs"][0]

    snap = await _wait_job(client, job_id)
    assert snap["status"] == "completed", snap.get("error")
    assert snap["title"]
    kinds = {d["kind"] for d in snap["documents"]}
    assert kinds == {"cv", "letter", "message"}
    cv_doc = next(d for d in snap["documents"] if d["kind"] == "cv")
    assert cv_doc["score_after"] is not None and cv_doc["score_before"] is not None
    assert cv_doc["score_after"] >= cv_doc["score_before"]

    # Fetch the document with its preview.
    r = await client.get(f"/api/documents/{cv_doc['id']}")
    assert r.status_code == 200
    doc = r.json()
    assert doc["mode"] == "data"
    assert doc["source"] and "#import" in doc["source"]
    assert doc["svgs"] and doc["svgs"][0].startswith("<svg")

    # Structured update: change the accent + template.
    new_settings = {**doc["settings"], "accent": "#E11D48", "template": "classic"}
    r = await client.put(f"/api/documents/{cv_doc['id']}", json={"settings": new_settings})
    assert r.status_code == 200, r.text
    assert r.json()["svgs"]

    # Source-mode edit: rename, recompile, persist.
    edited_source = r.json()["source"].replace('"Alex', '"Axel')
    r = await client.post(f"/api/documents/{cv_doc['id']}/compile", json={"source": edited_source})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] and body["saved"] and body["mode"] == "source"

    # Chat edit (offline appends an edit comment in source mode).
    r = await client.post(f"/api/documents/{cv_doc['id']}/chat", json={"message": "tighten the summary"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"]

    # PDF download.
    r = await client.get(f"/api/documents/{cv_doc['id']}/pdf")
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")
    assert "CV - " in r.headers["content-disposition"]

    # Source download + history + quota usage.
    r = await client.get(f"/api/documents/{cv_doc['id']}/source.typ")
    assert r.status_code == 200
    r = await client.get("/api/history")
    assert r.status_code == 200 and len(r.json()) == 1
    me = await client.get("/api/auth/me")
    assert me.json()["quota"]["used_today"] == 1


async def test_generate_in_german(client):
    await _register(client)
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "cv_text": SAMPLE_CV_TEXT, "language": "de",
              "template": "onyx"},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["jobs"][0]
    snap = await _wait_job(client, job_id)
    assert snap["status"] == "completed", snap.get("error")
    assert snap["language"] == "de"
    letter = next(d for d in snap["documents"] if d["kind"] == "letter")
    r = await client.get(f"/api/documents/{letter['id']}")
    assert r.status_code == 200
    doc = r.json()
    # Offline provider writes the German letter; the source embeds its data.
    assert "Sehr geehrte Damen und Herren" in doc["source"]
    assert 'lang: "de"' in doc["source"]


async def test_guest_flow_and_limit(client):
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "cv_text": SAMPLE_CV_TEXT, "language": "en",
              "template": "onyx"},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["jobs"][0]
    snap = await _wait_job(client, job_id)
    assert snap["status"] == "completed"

    # Guests get exactly one per day.
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "cv_text": SAMPLE_CV_TEXT, "template": "onyx"},
    )
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "guest_limit"


async def test_validation_errors(client):
    r = await client.post("/api/generate", json={"job_descriptions": ["too short"], "cv_text": "x"})
    assert r.status_code == 422

    r = await client.post("/api/auth/register", json={"email": "bad", "password": "longpassword1"})
    assert r.status_code == 422

    email = unique_email()
    await _register(client, email)
    r = await client.post("/api/auth/register", json={"email": email, "password": "longpassword1"})
    assert r.status_code == 409


async def test_api_healthz_pings_db(client):
    r = await client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "db": True}


async def test_config_public(client):
    r = await client.get("/api/config")
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["ai_mode"] == "offline"
    assert {t["id"] for t in cfg["templates"]} == {"onyx", "classic", "compact"}
    assert any(p["key"] == "plus" for p in cfg["plans"])


async def test_chat_source_edit_repair_round(client, monkeypatch):
    """A source-mode chat edit that does not compile gets ONE repair round
    with the compiler diagnostics; if the repair compiles it is applied,
    otherwise the edit is rejected with diagnostics."""
    from backend.app.ai.fake import FakeProvider

    await _register(client)
    r = await client.post("/api/cvs", json={"name": "Main", "raw_text": SAMPLE_CV_TEXT})
    cv_id = r.json()["id"]
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "master_cv_id": cv_id, "language": "en"},
    )
    snap = await _wait_job(client, r.json()["jobs"][0])
    assert snap["status"] == "completed", snap.get("error")
    cv_doc = next(d for d in snap["documents"] if d["kind"] == "cv")

    r = await client.get(f"/api/documents/{cv_doc['id']}")
    good_source = r.json()["source"]
    r = await client.post(f"/api/documents/{cv_doc['id']}/compile", json={"source": good_source})
    assert r.json()["saved"] and r.json()["mode"] == "source"

    async def broken_edit(self, source, instruction):
        return "#broken("

    async def broken_repair(self, source, diagnostics):
        assert "error" in diagnostics.lower()
        return "#still_broken("

    async def good_repair(self, source, diagnostics):
        return good_source

    # Edit and repair both broken -> rejected with diagnostics.
    monkeypatch.setattr(FakeProvider, "edit_source", broken_edit)
    monkeypatch.setattr(FakeProvider, "repair_source", broken_repair)
    r = await client.post(f"/api/documents/{cv_doc['id']}/chat", json={"message": "make it pop"})
    assert r.status_code == 200
    assert r.json()["ok"] is False and r.json()["diagnostics"]

    # Repair succeeds -> edit applied and recompiled.
    monkeypatch.setattr(FakeProvider, "repair_source", good_repair)
    r = await client.post(f"/api/documents/{cv_doc['id']}/chat", json={"message": "make it pop"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["svgs"]

    # Message docs route through the plain-text editor, not the Typst one.
    msg_doc = next(d for d in snap["documents"] if d["kind"] == "message")
    r = await client.post(f"/api/documents/{msg_doc['id']}/chat", json={"message": "shorter"})
    assert r.status_code == 200
    assert "[edited: shorter]" in r.json()["text_content"]
