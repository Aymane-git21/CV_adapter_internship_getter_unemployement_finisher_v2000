"""Provider protocol. Every method returns validated pydantic objects —
the LLM never emits raw markup, only structured data."""
from typing import Protocol

from ..schemas import CVData, JobAnalysis, LetterData


class AIError(Exception):
    """User-presentable AI failure (quota, invalid key, safety block...)."""

    def __init__(self, message: str, *, byok: bool = False):
        super().__init__(message)
        self.byok = byok


class AIProvider(Protocol):
    async def analyze(self, jd: str, cv_text: str, language: str) -> JobAnalysis: ...

    async def parse_cv(self, raw_text: str | None, pdf_bytes: bytes | None, language: str) -> CVData: ...

    async def tailor_cv(self, jd: str, analysis: JobAnalysis, master: CVData, language: str) -> CVData: ...

    async def write_letter(
        self, jd: str, analysis: JobAnalysis, cv: CVData, language: str
    ) -> LetterData: ...

    async def outreach(self, jd: str, analysis: JobAnalysis, cv: CVData, language: str) -> str: ...

    async def edit_cv_data(self, cv: CVData, instruction: str, language: str) -> CVData: ...

    async def edit_letter_data(self, letter: LetterData, instruction: str, language: str) -> LetterData: ...

    async def edit_source(self, source: str, instruction: str) -> str: ...

    async def validate_key(self) -> bool: ...
