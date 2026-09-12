"""The keyword match follows every edit: the structured form (PUT data), the
source editor (compile with a source), and the assistant (chat, in data and
source mode), in both directions. Switching editors alone never moves it,
and documents that are not CVs never get one."""
import asyncio

import pytest

from backend.app.ai.fake import FakeProvider
from backend.app.schemas import JobAnalysis, Keyword

from .conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email

# Python and Kubernetes are in the sample CV's own bullets; Rust only ever
# arrives through the offline tailor's "Key match" skills group.
_KEYWORDS = [
    Keyword(term="Python", weight=3),
    Keyword(term="Kubernetes", weight=2),
    Keyword(term="Rust", weight=1),
]
_WITHOUT_RUST = round(100 * 5 / 6)


@pytest.fixture()
def fixed_analysis(monkeypatch):
    async def analyze(self, jd, cv_text, language):
        return JobAnalysis(job_title="ML Engineer", company="Lumina", keywords=_KEYWORDS, notes="n")

    monkeypatch.setattr(FakeProvider, "analyze", analyze)


async def _generated_docs(client) -> dict[str, dict]:
    r = await client.post(
        "/api/auth/register", json={"email": unique_email(), "password": "longpassword1"}
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/generate",
        json={"job_descriptions": [SAMPLE_JD], "cv_text": SAMPLE_CV_TEXT, "language": "en",
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
    docs = {}
    for d in snap["documents"]:
        docs[d["kind"]] = (await client.get(f"/api/documents/{d['id']}?include_svg=false")).json()
    return docs


def _drop_key_match(data: dict) -> dict:
    return {**data, "skills": [g for g in data["skills"] if g["category"] != "Key match"]}


async def test_generation_scores_with_the_same_text_rescoring_reads(client, fixed_analysis):
    cv = (await _generated_docs(client))["cv"]
    assert cv["score_before"] == _WITHOUT_RUST
    assert cv["score_after"] == 100 and cv["keywords"] == {
        "matched": ["Python", "Kubernetes", "Rust"], "missing": []}

    # Re-saving identical content must not move the score.
    r = await client.put(f"/api/documents/{cv['id']}", json={"data": cv["data"]})
    assert r.status_code == 200, r.text
    assert r.json()["score_after"] == 100


async def test_form_edits_rescore_both_ways(client, fixed_analysis):
    cv = (await _generated_docs(client))["cv"]

    r = await client.put(f"/api/documents/{cv['id']}", json={"data": _drop_key_match(cv["data"])})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["keywords"] == {"matched": ["Python", "Kubernetes"], "missing": ["Rust"]}
    assert body["score_after"] == _WITHOUT_RUST
    assert body["score_before"] == cv["score_before"], "before is the master CV, it never moves"

    persisted = (await client.get(f"/api/documents/{cv['id']}?include_svg=false")).json()
    assert persisted["score_after"] == _WITHOUT_RUST and persisted["keywords"]["missing"] == ["Rust"]

    restored = _drop_key_match(cv["data"])
    restored["skills"] = [*restored["skills"], {"category": "Systems", "items": ["Rust"]}]
    r = await client.put(f"/api/documents/{cv['id']}", json={"data": restored})
    assert r.json()["score_after"] == 100 and r.json()["keywords"]["missing"] == []


async def test_source_edits_rescore_and_failed_compiles_do_not(client, fixed_analysis):
    cv = (await _generated_docs(client))["cv"]
    source = cv["source"]
    assert source.count('"Rust"') == 1

    r = await client.post(
        f"/api/documents/{cv['id']}/compile", json={"source": source.replace('"Rust"', '"Ruby"')}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] and body["mode"] == "source"
    assert body["score_after"] == _WITHOUT_RUST and body["keywords"]["missing"] == ["Rust"]

    r = await client.post(
        f"/api/documents/{cv['id']}/compile", json={"source": source + "\n#broken("}
    )
    body = r.json()
    assert body["saved"] is False
    assert body["score_after"] == _WITHOUT_RUST, "an unsaved source must not re-score"


async def test_switching_to_the_source_editor_alone_keeps_the_score(client, fixed_analysis):
    cv = (await _generated_docs(client))["cv"]
    r = await client.put(f"/api/documents/{cv['id']}", json={"data": _drop_key_match(cv["data"])})
    rendered = r.json()
    assert rendered["score_after"] == _WITHOUT_RUST

    r = await client.post(f"/api/documents/{cv['id']}/compile", json={"source": rendered["source"]})
    body = r.json()
    assert body["saved"] and body["mode"] == "source"
    assert body["score_after"] == _WITHOUT_RUST
    assert body["keywords"] == rendered["keywords"]


async def test_assistant_edits_rescore_in_data_mode(client, fixed_analysis, monkeypatch):
    cv = (await _generated_docs(client))["cv"]

    async def drop_rust(self, cv_data, instruction, language):
        out = cv_data.model_copy(deep=True)
        out.skills = [g for g in out.skills if g.category != "Key match"]
        return out

    monkeypatch.setattr(FakeProvider, "edit_cv_data", drop_rust)
    r = await client.post(f"/api/documents/{cv['id']}/chat", json={"message": "drop the key match group"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"]
    assert body["score_after"] == _WITHOUT_RUST and body["keywords"]["missing"] == ["Rust"]


async def test_assistant_edits_rescore_in_source_mode(client, fixed_analysis, monkeypatch):
    cv = (await _generated_docs(client))["cv"]
    r = await client.post(f"/api/documents/{cv['id']}/compile", json={"source": cv["source"]})
    assert r.json()["mode"] == "source" and r.json()["score_after"] == 100

    async def rust_to_ruby(self, source, instruction):
        return source.replace('"Rust"', '"Ruby"')

    monkeypatch.setattr(FakeProvider, "edit_source", rust_to_ruby)
    r = await client.post(f"/api/documents/{cv['id']}/chat", json={"message": "swap Rust for Ruby"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] and body["mode"] == "source"
    assert body["score_after"] == _WITHOUT_RUST and body["keywords"]["missing"] == ["Rust"]


async def test_letters_never_get_a_keyword_match(client, fixed_analysis):
    letter = (await _generated_docs(client))["letter"]
    assert letter["score_after"] is None and letter["keywords"] is None
    data = {**letter["data"], "subject": "Rust, Python and Kubernetes"}
    r = await client.put(f"/api/documents/{letter['id']}", json={"data": data})
    assert r.status_code == 200, r.text
    assert r.json()["score_after"] is None and r.json()["keywords"] is None
