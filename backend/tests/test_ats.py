from backend.app.ats import score
from backend.app.schemas import Keyword


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
