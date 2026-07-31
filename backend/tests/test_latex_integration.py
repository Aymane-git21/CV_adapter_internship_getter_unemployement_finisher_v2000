"""Gate tests for the LaTeX compiler integration: plan gating, coercions,
engine dispatch, .tex download, chat rules. The latexc HTTP client is
monkeypatched (real compiles live in services/latexc/tests)."""
import asyncio

import pytest
from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.db import session_factory
from backend.app.models import User
from backend.app.typstsvc.renderer import CompileResult

from .conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email

FAKE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="595pt" height="841pt"></svg>'


@pytest.fixture()
def latex_env(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "latexc_url", "http://latexc.test")
    monkeypatch.setattr(s, "latexc_token", "test-token")

    calls = {"n": 0}

    async def fake_compile_tex_measured(doc_id: str, tex_source: str):
        # One page at a healthy fill: the fit loop settles on the first attempt,
        # and continuous mode trims once (total in pt).
        calls["n"] += 1
        return (
            CompileResult(ok=True, pages=1, pdf=b"%PDF-fake", svgs=[FAKE_SVG]),
            tex_source,
            0.95,
            700.0,
        )

    # The single choke point: the compile_tex wrapper, the fit loop, and the
    # job pipeline all route through client.compile_tex_measured.
    monkeypatch.setattr(
        "backend.app.texsvc.client.compile_tex_measured", fake_compile_tex_measured
    )
    return calls


async def _register(client, email=None):
    r = await client.post(
        "/api/auth/register", json={"email": email or unique_email(), "password": "longpassword1"}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _upgrade(email: str, plan: str) -> None:
    async with session_factory()() as s:
        user = (await s.execute(select(User).where(User.email == email))).scalar_one()
        user.plan = plan
        await s.commit()


async def _make_cv_doc(client) -> dict:
    r = await client.post("/api/cvs", json={"name": "Main", "raw_text": SAMPLE_CV_TEXT})
    cv_id = r.json()["id"]
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "master_cv_id": cv_id, "language": "en",
              "template": "onyx", "accent": "#C2551B"},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["jobs"][0]
    for _ in range(120):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.4)
    assert snap["status"] == "completed", snap.get("error")
    return next(d for d in snap["documents"] if d["kind"] == "cv")


def _to_latex(settings: dict) -> dict:
    return {**settings, "compiler": "latex"}


async def test_latex_locked_for_free_plan(client, latex_env):
    await _register(client)
    doc = await _make_cv_doc(client)
    full = (await client.get(f"/api/documents/{doc['id']}")).json()
    r = await client.put(f"/api/documents/{doc['id']}", json={"settings": _to_latex(full["settings"])})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "latex_locked"


async def test_latex_flow_for_plus_plan(client, latex_env):
    email = unique_email()
    await _register(client, email)
    await _upgrade(email, "plus")
    doc = await _make_cv_doc(client)
    doc_id = doc["id"]
    full = (await client.get(f"/api/documents/{doc_id}")).json()

    # switch to latex: coercions + tex source + fake svgs served. Continuous
    # survives (two-pass trim); the photo coercion stays.
    r = await client.put(
        f"/api/documents/{doc_id}",
        json={"settings": {**_to_latex(full["settings"]), "page_mode": "continuous", "show_photo": True}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["settings"]["compiler"] == "latex"
    assert body["settings"]["page_mode"] == "continuous", "latex supports continuous now"
    assert body["settings"]["show_photo"] is False
    assert body["source"].startswith("\\documentclass")
    assert "paperheight=" in body["source"], "continuous latex source carries the trimmed height"
    assert body["svgs"] == [FAKE_SVG]
    assert latex_env["n"] >= 2, "continuous renders in two passes"

    # .tex download exists, .typ semantics preserved for typst docs only
    r = await client.get(f"/api/documents/{doc_id}/source.tex")
    assert r.status_code == 200
    assert r.headers["content-disposition"].endswith('.tex"')
    assert r.text.startswith("\\documentclass")

    # PDF comes from the latex path and is cached
    r = await client.get(f"/api/documents/{doc_id}/pdf")
    assert r.status_code == 200 and r.content == b"%PDF-fake"

    # chat in data mode re-renders through latex
    r = await client.post(f"/api/documents/{doc_id}/chat", json={"message": "tighten summary"})
    assert r.status_code == 200 and r.json()["ok"]

    # hand-edited tex persists as source mode
    edited = body["source"] + "\n% hand edit\n"
    r = await client.post(f"/api/documents/{doc_id}/compile", json={"source": edited})
    assert r.status_code == 200, r.text
    assert r.json()["saved"] and r.json()["mode"] == "source"

    # chat on hand-edited latex is refused (no AI repair on raw LaTeX)
    r = await client.post(f"/api/documents/{doc_id}/chat", json={"message": "anything"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "chat_source_latex"


async def test_latex_write18_rejected_at_api(client, latex_env):
    email = unique_email()
    await _register(client, email)
    await _upgrade(email, "plus")
    doc = await _make_cv_doc(client)
    full = (await client.get(f"/api/documents/{doc['id']}")).json()
    r = await client.put(f"/api/documents/{doc['id']}", json={"settings": _to_latex(full["settings"])})
    assert r.status_code == 200
    src = r.json()["source"] + "\n\\immediate\\write18{id}\n"
    r = await client.post(f"/api/documents/{doc['id']}/compile", json={"source": src})
    assert r.status_code == 422


async def test_latex_coerced_for_letters_and_wrong_template(client, latex_env):
    email = unique_email()
    await _register(client, email)
    await _upgrade(email, "plus")
    r = await client.post("/api/cvs", json={"name": "Main", "raw_text": SAMPLE_CV_TEXT})
    cv_id = r.json()["id"]
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "master_cv_id": cv_id, "language": "en",
              "template": "onyx", "accent": "#C2551B"},
    )
    job_id = r.json()["jobs"][0]
    for _ in range(120):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.4)
    letter = next(d for d in snap["documents"] if d["kind"] == "letter")
    full = (await client.get(f"/api/documents/{letter['id']}")).json()
    r = await client.put(f"/api/documents/{letter['id']}", json={"settings": _to_latex(full["settings"])})
    assert r.status_code == 200
    assert r.json()["settings"]["compiler"] == "typst", "letters are typst-only in v1"

    cv = next(d for d in snap["documents"] if d["kind"] == "cv")
    full = (await client.get(f"/api/documents/{cv['id']}")).json()
    classic = {**_to_latex(full["settings"]), "template": "classic"}
    r = await client.put(f"/api/documents/{cv['id']}", json={"settings": classic})
    assert r.status_code == 200
    assert r.json()["settings"]["compiler"] == "typst", "latex is onyx-only in v1"


async def test_latex_disabled_without_service_url(client):
    # no latex_env fixture: latexc_url is unset -> feature dark
    r = await client.get("/api/config")
    assert r.json()["latex_enabled"] is False
    email = unique_email()
    await _register(client, email)
    await _upgrade(email, "pro")
    doc = await _make_cv_doc(client)
    full = (await client.get(f"/api/documents/{doc['id']}")).json()
    r = await client.put(f"/api/documents/{doc['id']}", json={"settings": _to_latex(full["settings"])})
    assert r.status_code == 200
    assert r.json()["settings"]["compiler"] == "typst"


async def test_generation_with_latex_compiler(client, latex_env):
    email = unique_email()
    await _register(client, email)
    await _upgrade(email, "pro")
    r = await client.post("/api/cvs", json={"name": "Main", "raw_text": SAMPLE_CV_TEXT})
    cv_id = r.json()["id"]
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "master_cv_id": cv_id, "language": "en",
              "template": "onyx", "accent": "#C2551B", "compiler": "latex"},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["jobs"][0]
    for _ in range(120):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.4)
    assert snap["status"] == "completed", snap.get("error")
    cv = next(d for d in snap["documents"] if d["kind"] == "cv")
    letter = next(d for d in snap["documents"] if d["kind"] == "letter")

    full = (await client.get(f"/api/documents/{cv['id']}")).json()
    assert full["settings"]["compiler"] == "latex"
    assert full["source"].startswith("\\documentclass")
    assert full["svgs"] == [FAKE_SVG]

    lfull = (await client.get(f"/api/documents/{letter['id']}")).json()
    assert lfull["settings"].get("compiler", "typst") == "typst", "letters stay on typst"


async def test_generation_latex_downgrades_for_free_plan(client, latex_env):
    await _register(client)  # free plan
    r = await client.post("/api/cvs", json={"name": "Main", "raw_text": SAMPLE_CV_TEXT})
    cv_id = r.json()["id"]
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "master_cv_id": cv_id, "language": "en",
              "template": "onyx", "accent": "#C2551B", "compiler": "latex"},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["jobs"][0]
    for _ in range(120):
        snap = (await client.get(f"/api/jobs/{job_id}")).json()
        if snap["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.4)
    assert snap["status"] == "completed", snap.get("error")
    cv = next(d for d in snap["documents"] if d["kind"] == "cv")
    full = (await client.get(f"/api/documents/{cv['id']}")).json()
    assert full["settings"].get("compiler", "typst") == "typst", "silent downgrade for free plan"


async def test_config_and_me_expose_latex(client, latex_env):
    r = await client.get("/api/config")
    assert r.json()["latex_enabled"] is True
    email = unique_email()
    await _register(client, email)
    me = (await client.get("/api/auth/me")).json()
    assert me["quota"]["latex"] is False
    await _upgrade(email, "plus")
    me = (await client.get("/api/auth/me")).json()
    assert me["quota"]["latex"] is True
