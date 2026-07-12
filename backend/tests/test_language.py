"""Language plumbing — letter dates, prompt language names, offline provider
output for every supported document language (en/fr/de)."""
from datetime import UTC, datetime

from backend.app.ai.fake import FakeProvider
from backend.app.ai.prompts import lang_name, letter_prompt
from backend.app.jobs import letter_date


def test_lang_name_supported_languages():
    assert lang_name("en") == "English"
    assert lang_name("fr") == "French"
    assert lang_name("de") == "German"
    assert lang_name("xx") == "English"  # unknown falls back


def test_letter_date_formats():
    now = datetime.now(UTC)
    en = letter_date("en", "Berlin")
    fr = letter_date("fr", "Paris")
    de = letter_date("de", "Berlin")
    assert en.startswith("Berlin, ") and str(now.year) in en
    assert fr.startswith("Paris, le ") and str(now.year) in fr
    assert de.startswith("Berlin, den ") and f"{now.day}." in de and str(now.year) in de
    # Without a city the German date drops the "den".
    de_bare = letter_date("de", "")
    assert not de_bare.startswith(", ") and f"{now.day}." in de_bare


def test_letter_prompt_localized_hints():
    en = letter_prompt("jd", "notes", "{}", "en")
    fr = letter_prompt("jd", "notes", "{}", "fr")
    de = letter_prompt("jd", "notes", "{}", "de")
    assert "cover letter" in en and "Hiring Team" in en
    assert "lettre de motivation" in fr and "Madame, Monsieur" in fr
    assert "Anschreiben" in de and "Sehr geehrte Damen und Herren" in de
    assert "Mit freundlichen Grüßen" in de


async def test_fake_provider_writes_german():
    provider = FakeProvider()
    analysis = await provider.analyze(
        "Wir suchen einen Entwickler für die Cloud und der Betrieb unserer Plattform.",
        "cv text",
        "de",
    )
    assert analysis.language_detected == "de"
    cv = await provider.parse_cv("Alex Martin\nEngineer\nBuilds things", None, "de")
    letter = await provider.write_letter("jd", analysis, cv, "de")
    assert letter.greeting.startswith("Sehr geehrte")
    assert letter.closing == "Mit freundlichen Grüßen"
    msg = await provider.outreach("jd", analysis, cv, "de")
    assert "beworben" in msg
