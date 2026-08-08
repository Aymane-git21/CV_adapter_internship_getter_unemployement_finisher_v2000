"""Provider contract for generated screening answers (offline fake)."""
from backend.app.ai import get_provider
from backend.app.schemas import CVData, FactsProfile, JobAnalysis, Keyword


async def test_fake_write_answers_contract():
    provider = get_provider(None)  # CVG_FAKE_AI=1 in tests -> FakeProvider
    analysis = JobAnalysis(job_title="ML Engineer", company="Lumina",
                           keywords=[Keyword(term="python"), Keyword(term="docker")])
    master = CVData(full_name="Alex Martin", summary="ML engineer, 4 years")
    doc = await provider.write_answers("We need python and docker.", analysis, master,
                                      FactsProfile(work_permit="EU citizen"), "en")
    assert len(doc.items) >= 2
    assert all(i.origin == "generated" for i in doc.items)
    assert all(i.question and i.answer for i in doc.items)
    # Deterministic: same input, same output.
    doc2 = await provider.write_answers("We need python and docker.", analysis, master,
                                       FactsProfile(work_permit="EU citizen"), "en")
    assert doc.model_dump() == doc2.model_dump()
