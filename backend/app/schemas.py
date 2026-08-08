"""Pydantic schemas — the single source of truth for the CVData/LetterData
contract shared by the AI pipeline, the Typst renderer, and the frontend."""
from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------------------------
# Document data contracts
# ---------------------------------------------------------------------------


class Contacts(BaseModel):
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str = ""
    school: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    details: list[str] = Field(default_factory=list)


class SkillGroup(BaseModel):
    category: str = ""
    items: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str = ""
    tech: str = ""
    description: str = ""


class LanguageItem(BaseModel):
    name: str = ""
    level: str = ""


class CertificationItem(BaseModel):
    name: str = ""
    issuer: str = ""
    year: str = ""


class CVData(BaseModel):
    full_name: str = ""
    headline: str = ""
    contacts: Contacts = Field(default_factory=Contacts)
    summary: str = ""
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)

    def plain_text(self) -> str:
        """Flatten every string for ATS keyword scanning."""
        parts: list[str] = [self.full_name, self.headline, self.summary]
        parts += [
            self.contacts.email, self.contacts.location, self.contacts.linkedin,
            self.contacts.github, self.contacts.website,
        ]
        for e in self.experience:
            parts += [e.title, e.company, e.location, *e.bullets]
        for ed in self.education:
            parts += [ed.degree, ed.school, *ed.details]
        for s in self.skills:
            parts += [s.category, *s.items]
        for p in self.projects:
            parts += [p.name, p.tech, p.description]
        parts += [lang.name for lang in self.languages]
        parts += self.interests
        parts += [c.name for c in self.certifications]
        return "\n".join(x for x in parts if x)


class LetterSender(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""


class LetterRecipient(BaseModel):
    name: str = ""
    company: str = ""
    address_lines: list[str] = Field(default_factory=list)


class LetterData(BaseModel):
    sender: LetterSender = Field(default_factory=LetterSender)
    recipient: LetterRecipient = Field(default_factory=LetterRecipient)
    date_str: str = ""
    subject: str = ""
    greeting: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    closing: str = ""
    signature: str = ""

    def plain_text(self) -> str:
        return "\n".join([self.subject, *self.paragraphs])


class DocSettings(BaseModel):
    template: str = "onyx"
    accent: str = "#0F62FE"
    density: str = "normal"  # normal | tight | xtight
    show_photo: bool = False
    font_scale: float = 1.0
    lang: str = "en"
    page_mode: str = "paged"  # paged | continuous
    compiler: str = "typst"  # typst | latex
    # Fit-loop output, written back like density/font_scale: the CV still runs
    # past one page at the tightest density and the smallest readable type, so
    # the content itself has to come down. The studio surfaces this.
    overflowed: bool = False


# ---------------------------------------------------------------------------
# AI analysis contracts
# ---------------------------------------------------------------------------


class Keyword(BaseModel):
    term: str
    weight: int = 1  # 1..3
    aliases: list[str] = Field(default_factory=list)


class JobAnalysis(BaseModel):
    job_title: str = "Job Application"
    company: str = ""
    language_detected: str = "en"
    keywords: list[Keyword] = Field(default_factory=list)
    recipient_name: str = ""
    recipient_address_lines: list[str] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# API payloads
# ---------------------------------------------------------------------------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginIn(BaseModel):
    credential: str


class FeedbackIn(BaseModel):
    name: str = ""
    email: str = ""
    message: str = Field(min_length=3, max_length=4000)


class MasterCVIn(BaseModel):
    name: str = "My CV"
    raw_text: str | None = None
    data: CVData | None = None


class GenerateIn(BaseModel):
    job_descriptions: list[str] = Field(min_length=1, max_length=10)
    master_cv_id: int | None = None
    cv_text: str | None = None  # inline paste (guests / first-time)
    language: str = "en"
    rewrite_intensity: str = "major"  # reshape | minor | major | max_ats
    compiler: str = "typst"  # typst | latex (latex: plus/pro + onyx, silent fallback)
    template: str = "onyx"
    accent: str = "#0F62FE"
    show_photo: bool = False
    photo_id: str | None = None
    save_master: bool = False


class DocumentUpdateIn(BaseModel):
    data: dict | None = None
    settings: DocSettings | None = None
    text_content: str | None = None


class CompileIn(BaseModel):
    source: str | None = None  # when provided, switches the document to source mode


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ByokValidateIn(BaseModel):
    key: str = Field(min_length=10, max_length=200)


# ---------------------------------------------------------------------------
# Auto-apply pipeline contracts
# ---------------------------------------------------------------------------


class JobPostingIn(BaseModel):
    """Normalized posting produced by every source adapter."""

    source: str
    external_id: str
    title: str
    company: str = ""
    location: str = ""
    contract_type: str = ""
    description: str
    apply_email: str | None = None
    apply_url: str | None = None
    posted_at: str = ""  # ISO date string from the source, informational
    raw: dict = Field(default_factory=dict)


class SavedSearchParams(BaseModel):
    keywords: str = ""
    insee: str = ""  # commune code, e.g. Toulouse
    radius_km: int = 20
    contract_type: str = ""  # source-specific filter, empty = all


class FactsProfile(BaseModel):
    """Deterministic answer material. Never invented by the model."""

    work_permit: str = ""
    notice_period: str = ""
    salary_range: str = ""
    mobility: str = ""
    languages: str = ""
    driving_licence: str = ""
    availability: str = ""


class AnswerItem(BaseModel):
    question: str
    answer: str
    origin: str = "generated"  # facts | generated


class AnswersDoc(BaseModel):
    items: list[AnswerItem] = Field(default_factory=list)


class GmailConnectIn(BaseModel):
    """OAuth code exchange for Gmail send access (Task 12)."""

    code: str = ""
    redirect_uri: str = ""
