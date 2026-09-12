from backend.app.ats import cover_all_keywords, matchable, score
from backend.app.doctext import cv_text
from backend.app.schemas import CVData, Keyword, SkillGroup


def test_basic_match_and_missing():
    kws = [Keyword(term="Python", weight=3), Keyword(term="Kubernetes", weight=2), Keyword(term="Rust", weight=1)]
    result = score(kws, "Seasoned python engineer deploying on Kubernetes clusters.")
    assert "Python" in result["matched"]
    assert "Kubernetes" in result["matched"]
    assert result["missing"] == ["Rust"]
    assert result["score"] == round(100 * 5 / 6)


def test_aliases_count():
    kws = [Keyword(term="Google Cloud", weight=2, aliases=["GCP"])]
    assert score(kws, "Deployed workloads on gcp with terraform")["score"] == 100


def test_accent_insensitive_french():
    kws = [Keyword(term="ingénierie", weight=1)]
    assert score(kws, "Diplome en ingenierie logicielle")["score"] == 100


def test_word_boundaries():
    kws = [Keyword(term="java", weight=1)]
    assert score(kws, "I love javascript only")["score"] == 0
    assert score(kws, "Java and javascript")["score"] == 100


def test_empty_keywords():
    assert score([], "anything")["score"] == 0


# ---- overboard backstop ------------------------------------------------------


def _cv_score(keywords, cv: CVData) -> dict:
    return score(keywords, cv_text(cv.model_dump()))


def test_cover_all_keywords_reaches_100_for_every_matchable_term():
    terms = [("Python", 3), ("C++", 2), ("C#", 1), (".NET", 1), ("CI/CD", 2), ("R&D", 1),
             ("e-commerce", 1), ("Node.js", 2), ("machine learning", 3), ("ingénierie", 1),
             ("Straße", 1), ("Go", 1)]
    kws = [Keyword(term=t, weight=w) for t, w in terms]
    cv = CVData(full_name="A", summary="Built things in Python.",
                skills=[SkillGroup(category="Tools", items=["Docker"])])
    assert _cv_score(kws, cv)["score"] < 100

    covered = cover_all_keywords(kws, cv, "en")
    result = _cv_score(kws, covered)
    assert result["score"] == 100 and result["missing"] == []
    assert covered.skills[0].category == "Tools" and covered.skills[0].items[0] == "Docker"
    assert "Python" not in covered.skills[0].items, "already-matched terms are not listed again"
    assert cv.skills[0].items == ["Docker"], "the input CV is not mutated"


def test_cover_all_keywords_creates_a_localized_group_without_skills():
    for lang, label in (("en", "Key skills"), ("fr", "Compétences clés"), ("de", "Kernkompetenzen")):
        covered = cover_all_keywords([Keyword(term="Kubernetes")], CVData(full_name="A"), lang)
        assert [(g.category, g.items) for g in covered.skills] == [(label, ["Kubernetes"])]


def test_cover_all_keywords_uses_a_matchable_alias_and_skips_the_impossible():
    kws = [Keyword(term="日本語", aliases=["Japanese"]), Keyword(term="🚀")]
    assert not matchable("日本語") and not matchable("🚀") and matchable("C#")
    covered = cover_all_keywords(kws, CVData(full_name="A"), "en")
    assert covered.skills[0].items == ["Japanese"]
    assert _cv_score(kws, covered)["missing"] == ["🚀"], "no text can ever match this term"


def test_cover_all_keywords_lists_equivalent_spellings_once():
    kws = [Keyword(term="CI/CD"), Keyword(term="CI CD")]
    covered = cover_all_keywords(kws, CVData(full_name="A"), "en")
    assert covered.skills[0].items == ["CI/CD"]
    assert _cv_score(kws, covered)["score"] == 100


def test_cover_all_keywords_returns_the_same_cv_when_nothing_is_missing():
    cv = CVData(full_name="A", skills=[SkillGroup(category="T", items=["Rust"])])
    assert cover_all_keywords([Keyword(term="Rust")], cv) is cv
