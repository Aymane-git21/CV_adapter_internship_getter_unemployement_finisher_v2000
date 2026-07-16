"""Gate pins for the AI prompts and the deterministic eval metrics.
Prompts are latent-space inputs; these tests pin their load-bearing mandates
so a wording edit can't silently revert them. The metric tests keep the
paid eval's scoring honest without any LLM call."""
from backend.app.ai import prompts
from backend.evals import metrics


def test_tailor_prompt_mandates_rewriting():
    p = prompts.tailor_cv_prompt("JD", "notes", ["python", "gcp"], "{}", "en")
    assert "WRITER, not a copyist" in p
    assert "FACTS are locked" in p
    assert "WORDING is yours" in p
    assert "NEVER invent" in p
    assert "python, gcp" in p
    assert "English" in p


def test_tailor_prompt_keeps_truth_and_style_rails():
    p = prompts.tailor_cv_prompt("JD", "notes", ["python"], "{}", "fr")
    assert "em dash" in p
    assert "ONE FULL PAGE" in p
    assert "French" in p


def test_bullet_novelty_scores_copy_vs_fresh():
    master = ["Built the evaluation harness that gates every prompt change in CI."]
    verbatim = metrics.bullet_novelty(master[0], master)
    fresh = metrics.bullet_novelty(
        "Designed demand forecasting models covering retail stores nationwide.", master
    )
    assert verbatim == 0.0
    assert fresh > 0.8
    assert metrics.bullet_novelty("anything", []) == 1.0


def test_fabricated_numbers_flags_invented_metrics_only():
    master = "Cut inference costs by 35%, serving 40k daily queries across 1,200 stores since 2021."
    ok = "Reduced serving costs 35% at 40k queries per day, covering 1 200 stores."
    bad = "Improved throughput 60% across 1,200 stores."
    assert metrics.fabricated_numbers(ok, [master]) == []
    assert metrics.fabricated_numbers(bad, [master]) == ["60"]
    # Leading zeros and reformatting are not fabrication.
    assert metrics.fabricated_numbers("07 releases", ["7 releases"]) == []
    assert metrics.fabricated_numbers("40,000 queries daily", ["40k queries/day"]) == []
