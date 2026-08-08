"""Screening answers, deterministic half. Fixed recruiter questions are
answered by copying the user's own facts — the model never touches them
(latent/deterministic split: same input, same output, no LLM)."""
from .schemas import AnswerItem, FactsProfile

FIXED_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "en": [
        ("work_permit", "Are you authorized to work in this country?"),
        ("notice_period", "What is your notice period?"),
        ("salary_range", "What are your salary expectations?"),
        ("mobility", "Are you willing to relocate or commute?"),
        ("languages", "Which languages do you speak?"),
        ("driving_licence", "Do you hold a driving licence?"),
        ("availability", "When can you start?"),
    ],
    "fr": [
        ("work_permit", "Êtes-vous autorisé(e) à travailler en France ?"),
        ("notice_period", "Quel est votre préavis ?"),
        ("salary_range", "Quelles sont vos prétentions salariales ?"),
        ("mobility", "Êtes-vous mobile ?"),
        ("languages", "Quelles langues parlez-vous ?"),
        ("driving_licence", "Avez-vous le permis de conduire ?"),
        ("availability", "Quand pouvez-vous commencer ?"),
    ],
    "de": [
        ("work_permit", "Sind Sie berechtigt, in diesem Land zu arbeiten?"),
        ("notice_period", "Wie lang ist Ihre Kündigungsfrist?"),
        ("salary_range", "Wie sind Ihre Gehaltsvorstellungen?"),
        ("mobility", "Sind Sie umzugsbereit bzw. mobil?"),
        ("languages", "Welche Sprachen sprechen Sie?"),
        ("driving_licence", "Besitzen Sie einen Führerschein?"),
        ("availability", "Wann können Sie anfangen?"),
    ],
}


def fixed_answers(facts: FactsProfile, language: str) -> list[AnswerItem]:
    questions = FIXED_QUESTIONS.get(language, FIXED_QUESTIONS["en"])
    out: list[AnswerItem] = []
    for field, question in questions:
        value = getattr(facts, field, "")
        if value:
            out.append(AnswerItem(question=question, answer=value, origin="facts"))
    return out
