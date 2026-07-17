"""Deterministic offline provider. Powers tests and keyless local dev: the
entire product flow works without a Gemini key — generation is heuristic
instead of smart, but the contracts are identical."""
import asyncio
import re

from ..schemas import (
    Contacts,
    CVData,
    ExperienceItem,
    JobAnalysis,
    Keyword,
    LetterData,
    LetterRecipient,
    SkillGroup,
)

_TECH_HINTS = [
    "python", "java", "typescript", "javascript", "react", "node", "sql", "postgres",
    "docker", "kubernetes", "gcp", "aws", "azure", "ml", "llm", "rag", "pytorch",
    "tensorflow", "spark", "airflow", "kafka", "api", "fastapi", "django", "flask",
    "unity", "c#", "c++", "vr", "ar", "agile", "ci/cd", "git", "linux", "mlops",
    "terraform", "go", "rust", "etl", "nlp", "vision", "data", "cloud",
]

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?:\+?\d[\d ()./-]{7,}\d)")


class FakeProvider:
    async def _tick(self):
        await asyncio.sleep(0.01)

    async def analyze(self, jd: str, cv_text: str, language: str) -> JobAnalysis:
        await self._tick()
        low = jd.lower()
        keywords = [
            Keyword(term=t, weight=2 if low.count(t) > 1 else 1)
            for t in _TECH_HINTS
            if t in low
        ][:16]
        if not keywords:
            keywords = [Keyword(term=w, weight=1) for w in sorted(set(low.split()))[:8] if len(w) > 5]
        title = "Job Application"
        m = re.search(r"(?:poste de|position:|role:|job title:?)\s*([^\n.,;]{4,60})", jd, re.I)
        if m:
            title = m.group(1).strip().title()
        company = ""
        m = re.search(r"(?:chez|at|company:|société)\s+([A-Z][\w&. -]{2,40})", jd)
        if m:
            company = m.group(1).strip()
        return JobAnalysis(
            job_title=title,
            company=company,
            language_detected=(
                "fr" if " le " in low and " et " in low
                else "de" if " und " in low and (" der " in low or " die " in low)
                else "en"
            ),
            keywords=keywords,
            notes="Deterministic offline analysis (no API key configured).",
        )

    async def parse_cv(self, raw_text: str | None, pdf_bytes: bytes | None, language: str) -> CVData:
        await self._tick()
        text = raw_text or ""
        if pdf_bytes is not None and not text:
            text = "Uploaded PDF (offline mode cannot read PDFs: paste text instead)"
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        name = lines[0][:60] if lines else "Your Name"
        email = (_EMAIL.search(text) or [None])
        email_val = email.group(0) if hasattr(email, "group") else ""
        phone = _PHONE.search(text)
        skills = [t for t in _TECH_HINTS if t in text.lower()][:10]
        bullets = [ln for ln in lines[1:] if len(ln) > 30][:4]
        return CVData(
            full_name=name,
            headline=lines[1][:80] if len(lines) > 1 else "",
            contacts=Contacts(email=email_val, phone=phone.group(0) if phone else ""),
            summary=" ".join(lines[2:4])[:300],
            experience=[
                ExperienceItem(
                    title="Experience (from pasted text)",
                    company="",
                    bullets=bullets or ["Paste a richer CV to fill this in."],
                )
            ],
            skills=[SkillGroup(category="Skills", items=skills or ["communication"])],
        )

    async def tailor_cv(self, jd: str, analysis: JobAnalysis, master: CVData, language: str) -> CVData:
        await self._tick()
        tailored = master.model_copy(deep=True)
        terms = [k.term for k in analysis.keywords][:8]
        if terms:
            tailored.skills = [SkillGroup(category="Key match", items=terms)] + tailored.skills
        target = analysis.job_title if analysis.job_title != "Job Application" else "this role"
        prefix = {"fr": "Profil ciblé : ", "de": "Zielprofil: "}.get(language, "Targeted profile: ")
        tailored.summary = f"{prefix}{target}. {master.summary}"[:500]
        return tailored

    async def write_letter(self, jd: str, analysis: JobAnalysis, cv: CVData, language: str) -> LetterData:
        await self._tick()
        company = analysis.company or {
            "fr": "votre entreprise", "de": "Ihr Unternehmen",
        }.get(language, "your company")
        if language == "de":
            return LetterData(
                recipient=LetterRecipient(name="Sehr geehrte Damen und Herren", company=analysis.company),
                subject=f"Bewerbung als {analysis.job_title}",
                greeting="Sehr geehrte Damen und Herren,",
                paragraphs=[
                    f"Ihre Ausschreibung für die Position {analysis.job_title} hat mein Interesse geweckt, da mein Profil eng zu Ihren Anforderungen passt.",
                    f"Meine im Lebenslauf beschriebenen Erfahrungen decken die Kernkompetenzen ab, die {company} sucht.",
                    "Über die Gelegenheit zu einem persönlichen Gespräch freue ich mich sehr.",
                ],
                closing="Mit freundlichen Grüßen",
            )
        if language == "fr":
            return LetterData(
                recipient=LetterRecipient(name="Madame, Monsieur", company=analysis.company),
                subject=f"Objet : Candidature au poste de {analysis.job_title}",
                greeting="Madame, Monsieur,",
                paragraphs=[
                    f"Votre offre pour le poste de {analysis.job_title} a retenu toute mon attention, et mon parcours correspond étroitement à vos attentes.",
                    f"Mes expériences décrites dans mon CV démontrent les compétences clés recherchées par {company}.",
                    "Je serais ravi d'échanger avec vous pour vous présenter ma motivation de vive voix.",
                ],
                closing="Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.",
            )
        return LetterData(
            recipient=LetterRecipient(name="Hiring Team", company=analysis.company),
            subject=f"Re: Application | {analysis.job_title}",
            greeting="Dear Hiring Team,",
            paragraphs=[
                f"The {analysis.job_title} opening caught my attention because it matches my background closely.",
                f"My experience, summarized in my CV, maps directly onto what {company} is looking for.",
                "I would welcome a conversation about how I can contribute. Thank you for your consideration.",
            ],
            closing="Yours sincerely,",
        )

    async def outreach(self, jd: str, analysis: JobAnalysis, cv: CVData, language: str) -> str:
        await self._tick()
        if language == "de":
            return (
                f"Guten Tag, ich habe mich soeben auf die Position {analysis.job_title} beworben. "
                "Mein Profil passt eng zu Ihren Anforderungen. Hätten Sie 15 Minuten für ein kurzes Gespräch?"
            )
        if language == "fr":
            return (
                f"Bonjour, je viens de postuler au poste de {analysis.job_title}. "
                "Mon profil correspond étroitement à vos besoins. Seriez-vous disponible pour un échange de 15 minutes ?"
            )
        return (
            f"Hi, I just applied for the {analysis.job_title} role. "
            "My background matches the requirements closely; open to a quick 15-minute chat?"
        )

    async def edit_cv_data(self, cv: CVData, instruction: str, language: str) -> CVData:
        await self._tick()
        edited = cv.model_copy(deep=True)
        edited.summary = (edited.summary + f" [edited: {instruction[:60]}]").strip()
        return edited

    async def edit_letter_data(self, letter: LetterData, instruction: str, language: str) -> LetterData:
        await self._tick()
        edited = letter.model_copy(deep=True)
        if edited.paragraphs:
            edited.paragraphs[-1] = (edited.paragraphs[-1] + f" [edited: {instruction[:60]}]").strip()
        return edited

    async def edit_source(self, source: str, instruction: str) -> str:
        await self._tick()
        return source + f"\n// edit requested: {instruction[:80]}\n"

    async def repair_source(self, source: str, diagnostics: str) -> str:
        await self._tick()
        return source

    async def edit_message(self, text: str, instruction: str) -> str:
        await self._tick()
        return (text + f" [edited: {instruction[:60]}]").strip()

    async def validate_key(self) -> bool:
        await self._tick()
        return True
