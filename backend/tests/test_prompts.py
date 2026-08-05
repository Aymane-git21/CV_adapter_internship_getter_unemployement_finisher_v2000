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
    assert "ONE PAGE" in p
    assert "French" in p


def test_tailor_prompt_states_a_measured_page_budget():
    """The old rule told the model to keep 3-5 entries with 3-4 bullets each
    AND everything else, which is how a CV overflowed to two pages. The budget
    below is measured against the real template: 10 content lines fill a page
    at `tight`, 15 is the ceiling at `xtight`."""
    p = prompts.tailor_cv_prompt("JD", "notes", ["python"], "{}", "en")
    assert "CONTENT LINES" in p and "Start from 12" in p
    # A flat number is wrong: the same page carries 15 content lines for a lean
    # CV and 8 for one with 4 roles, 3 degrees and 4 skill groups.
    assert "1 for each experience entry beyond 3" in p
    assert "1 for each education entry beyond 2" in p
    assert "1 for each skill group beyond 3" in p
    assert "at most 4 experience entries" in p and "at most 3 projects" in p
    assert "Cutting is the job" in p
    assert "half-empty page fails" in p, "must not overcorrect into a sparse CV"


def test_tailor_prompt_bans_filler_and_uniform_bullets():
    p = prompts.tailor_cv_prompt("JD", "notes", ["python"], "{}", "en")
    assert "BANNED WORDING" in p
    for word in ("robust", "comprehensive", "production-grade", "passionate"):
        assert word in p
    assert "VARY THE" in p
    assert "AT MOST HALF" in p, "the shape rule needs a countable cap"
    assert "same verb" in p


def test_tailor_prompt_requires_defensible_skills_and_lean_education():
    p = prompts.tailor_cv_prompt("JD", "notes", ["python"], "{}", "en")
    assert "every item must be defensible" in p
    assert "could not be questioned on" in p, "skills must survive an interview"
    assert "studied X, Y and Z" in p, "generic education filler must be banned"


def test_tailor_prompt_intensity_mandates():
    levels = ("reshape", "minor", "major", "max_ats")
    p = {
        lv: prompts.tailor_cv_prompt("JD", "notes", ["python"], "{}", "en", rewrite_intensity=lv)
        for lv in levels
    }
    # Default (5 positional args, today's call shape) must reproduce "major".
    assert prompts.tailor_cv_prompt("JD", "notes", ["python"], "{}", "en") == p["major"]
    assert "not a copyist" in p["major"]
    assert "not a copyist" in p["max_ats"]
    for lv in levels:
        assert "FACTS are locked" in p[lv]
    assert [lv for lv in levels if "EDITOR, not a writer" in p[lv]] == ["reshape"]
    assert [lv for lv in levels if "MAXIMIZE ATS COVERAGE" in p[lv]] == ["max_ats"]
    # Unknown level falls back to the default mandate.
    bad = prompts.tailor_cv_prompt("JD", "notes", ["python"], "{}", "en", rewrite_intensity="turbo")
    assert bad == p["major"]


def test_source_prompts_carry_typst_primer():
    p = prompts.edit_source_prompt("SRC", "make headings blue")
    assert "TYPST IS NOT LATEX" in p
    assert 'single-element array MUST be ("a",)' in p
    assert "SETTINGS KNOBS" in p
    assert "DATA KEYS" in p
    r = prompts.repair_source_prompt("SRC", "error: unclosed delimiter")
    assert "COMPILER ERRORS" in r
    assert "SMALLEST" in r
    assert "TYPST IS NOT LATEX" in r


def test_message_edit_prompt_is_plain_text():
    m = prompts.edit_message_prompt("hello recruiter", "make it shorter")
    assert "typst" not in m.lower()
    assert "700" in m


def test_bullet_novelty_scores_copy_vs_fresh():
    master = ["Built the evaluation harness that gates every prompt change in CI."]
    verbatim = metrics.bullet_novelty(master[0], master)
    fresh = metrics.bullet_novelty(
        "Designed demand forecasting models covering retail stores nationwide.", master
    )
    assert verbatim == 0.0
    assert fresh > 0.8
    assert metrics.bullet_novelty("anything", []) == 1.0


def test_content_lines_counts_what_the_page_budget_spends():
    cv = {
        "experience": [{"bullets": ["a", "b", "c"]}, {"bullets": ["d"]}],
        "projects": [{"description": "e"}, {"description": "  "}, {}],
    }
    assert metrics.content_lines(cv) == 5  # 4 bullets + 1 non-empty description
    assert metrics.content_lines({}) == 0


def test_em_dash_fields_reports_where_not_just_whether():
    cv = {"headline": "Engineer — Systems", "summary": "clean",
          "experience": [{"bullets": ["fine", "also — not"]}]}
    assert metrics.em_dash_fields(cv) == ["headline", "experience[0].bullets[1]"]
    assert metrics.em_dash_fields({"summary": "clean"}) == []
    # a value inherited verbatim from the master is a locked fact, not wording
    inherited = {"experience": [{"title": "Research Intern — Computer Vision"}]}
    assert metrics.em_dash_fields(inherited, 'x "Research Intern — Computer Vision" y') == []
    assert metrics.em_dash_fields(inherited, "unrelated master") == ["experience[0].title"]


def test_content_line_budget_shrinks_as_the_furniture_grows():
    """The page is shared: a lean CV fits 15 content lines, one with 4 roles,
    3 degrees and 4 skill groups only 8, so the budget cannot be a constant."""
    lean = {"experience": [{}] * 3, "education": [{}] * 2, "skills": [{}] * 3}
    heavy = {"experience": [{}] * 4, "education": [{}] * 3, "skills": [{}] * 4}
    assert metrics.content_line_budget(lean) == 12
    assert metrics.content_line_budget(heavy) == 9
    assert metrics.content_line_budget({}) == 12
    # never collapses to an unusable budget
    assert metrics.content_line_budget({"experience": [{}] * 9, "skills": [{}] * 9}) == 6


def test_filler_words_flags_only_what_the_model_added():
    master = "Built a robust ingestion pipeline."
    tailored = "Built a robust, comprehensive pipeline leveraging advanced tooling."
    # "robust" is the candidate's own word, the other three are inflation.
    assert metrics.filler_words(tailored, master) == ["advanced", "comprehensive", "leverage"]
    assert metrics.filler_words("Cut release time from days to hours.", master) == []


def test_purpose_clause_fraction_detects_the_uniform_template():
    uniform = [
        "Centralized enterprise workflows across systems to create a unified source.",
        "Deployed backend services on OpenShift, ensuring high availability.",
        "Designed automated pipelines to guarantee zero-downtime releases.",
    ]
    varied = [
        "Cut LLM serving costs 35% by routing between fine-tuned and frontier models.",
        "Shipped forecasting models covering 1,200 stores; stockouts fell 18%.",
        "Built the evaluation harness that gates every prompt change in CI.",
    ]
    assert metrics.purpose_clause_fraction(uniform) == 1.0
    assert metrics.purpose_clause_fraction(varied) < 0.5
    assert metrics.purpose_clause_fraction([]) == 0.0


def test_purpose_clause_ignores_the_preposition_to():
    """A bare "to <word>" also matches prepositions, which scored good bullets
    as template-shaped and failed eval runs that were fine."""
    prepositions = [
        "Cut serving costs 35% by routing traffic to fine-tuned small models.",
        "Migrated the ingestion tier to Kubernetes; deploy time fell days to hours.",
        "Shipped the release pipeline end to end across four squads.",
    ]
    assert metrics.purpose_clause_fraction(prepositions) == 0.0


def test_repeated_openers_catches_duplicate_verbs():
    assert metrics.repeated_openers(["Built X", "Built Y", "Shipped Z"]) == ["built"]
    assert metrics.repeated_openers(["Built X", "Shipped Y"]) == []


def test_unevidenced_skills_flags_invention_not_reformatting():
    cv = {
        "summary": "Platform engineer.",
        "experience": [{"title": "SRE", "company": "Acme",
                        "bullets": ["Ran Kubernetes clusters on GCP."]}],
        "skills": [{"category": "Infra",
                    "items": ["Kubernetes (GKE)", "Python", "Formal methods"]}],
    }
    master = "Python, Kubernetes, Terraform"
    # GKE parenthetical passes on "kubernetes"; "formal methods" is backed by nothing.
    assert metrics.unevidenced_skills(cv, master) == ["Formal methods"]
    assert metrics.unevidenced_skills({}, "") == []


def test_unevidenced_skills_allows_rewording_of_a_real_skill():
    """A master listing "monitoring & drift" may legitimately be retitled to
    "Model Monitoring" and "Drift Detection"; only invention is a defect."""
    cv = {"summary": "", "skills": [{"category": "MLOps", "items": [
        "Model Monitoring", "Drift Detection", "Telepathy"]}]}
    master = "MLOps: model monitoring & drift detection, CI/CD"
    assert metrics.unevidenced_skills(cv, master) == ["Telepathy"]


def test_fabricated_numbers_flags_invented_metrics_only():
    master = "Cut inference costs by 35%, serving 40k daily queries across 1,200 stores since 2021."
    ok = "Reduced serving costs 35% at 40k queries per day, covering 1 200 stores."
    bad = "Improved throughput 60% across 1,200 stores."
    assert metrics.fabricated_numbers(ok, [master]) == []
    assert metrics.fabricated_numbers(bad, [master]) == ["60"]
    # Leading zeros and reformatting are not fabrication.
    assert metrics.fabricated_numbers("07 releases", ["7 releases"]) == []
    assert metrics.fabricated_numbers("40,000 queries daily", ["40k queries/day"]) == []
