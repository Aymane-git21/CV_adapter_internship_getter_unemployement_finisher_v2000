"""Deterministic answers come from the facts profile, never the model."""
from backend.app.answers import FIXED_QUESTIONS, fixed_answers
from backend.app.schemas import FactsProfile
from backend.tests.conftest import unique_email


def test_fixed_answers_only_filled_fields_and_language():
    facts = FactsProfile(work_permit="EU citizen", notice_period="1 month")
    en = fixed_answers(facts, "en")
    assert [a.origin for a in en] == ["facts", "facts"]
    assert any("work" in a.question.lower() for a in en)
    fr = fixed_answers(facts, "fr")
    assert len(fr) == 2 and fr[0].question != en[0].question
    assert fixed_answers(FactsProfile(), "en") == []
    assert set(FIXED_QUESTIONS) == {"en", "fr", "de"}


async def test_facts_roundtrip_via_api(client):
    email, password = unique_email(), "password123"
    await client.post("/api/auth/register", json={"email": email, "password": password})
    r = await client.get("/api/account/facts")
    assert r.status_code == 200
    assert r.json()["work_permit"] == ""
    r2 = await client.put("/api/account/facts", json={"work_permit": "EU citizen", "salary_range": "45-55k EUR"})
    assert r2.status_code == 200
    r3 = await client.get("/api/account/facts")
    assert r3.json()["work_permit"] == "EU citizen"
    assert r3.json()["salary_range"] == "45-55k EUR"


async def test_facts_require_auth(client):
    r = await client.get("/api/account/facts")
    assert r.status_code in (401, 403)
