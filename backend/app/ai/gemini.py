"""Gemini provider — modern google-genai SDK, async, schema-enforced output."""
import asyncio
import json
import logging
import re
from typing import TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from ..config import get_settings
from ..schemas import CVData, JobAnalysis, LetterData
from . import prompts
from .base import AIError

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

_TIMEOUT = 90
_MAX_RETRY_SLEEP = 65.0

# Google's 429s carry the wait time two ways: a RetryInfo detail
# ("'retryDelay': '28.3s'") and prose ("Please retry in 28.343756161s").
_RETRY_DELAY = re.compile(r"retry(?:Delay'?:\s*'|\s+in\s+)([\d.]+)s", re.IGNORECASE)


def _retry_delay_seconds(exc: Exception) -> float | None:
    """Server-suggested backoff parsed from a Gemini 429, if present."""
    m = _RETRY_DELAY.search(str(exc))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


class GeminiProvider:
    def __init__(self, api_key: str | None):
        """api_key=None -> Vertex AI via the runtime service account (server
        traffic); a key -> AI Studio API (BYOK, or a key-configured server)."""
        settings = get_settings()
        if api_key:
            self._byok = api_key != settings.gemini_api_key
            self._client = genai.Client(api_key=api_key)
        else:
            self._byok = False
            self._client = genai.Client(
                vertexai=True,
                project=settings.gcp_project or None,
                location=settings.gcp_location or "global",
            )
        self._model = settings.gemini_model
        self._model_lite = settings.gemini_model_lite

    # -- low level -----------------------------------------------------------
    def _translate_error(self, exc: Exception) -> AIError:
        if isinstance(exc, genai_errors.APIError):
            code = getattr(exc, "code", None)
            if code in (401, 403):
                msg = "Gemini rejected the API key." + (
                    " Check the key you provided in Settings." if self._byok else ""
                )
                return AIError(msg, byok=self._byok)
            if code == 429:
                msg = (
                    "Your Gemini API key hit its rate/quota limit. Wait a minute or check your plan."
                    if self._byok
                    else "The AI service is at capacity right now. Try again shortly."
                )
                return AIError(msg, byok=self._byok)
            return AIError(f"AI service error ({code}). Try again shortly.", byok=self._byok)
        if isinstance(exc, asyncio.TimeoutError):
            return AIError("The AI took too long to respond. Try again.", byok=self._byok)
        return AIError("Unexpected AI failure. Try again.", byok=self._byok)

    async def _generate(self, contents, *, schema: type[T] | None = None, lite: bool = False, attempts_left: int = 2):
        model = self._model_lite if lite else self._model
        config = None
        if schema is not None:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            )
        try:
            resp = await asyncio.wait_for(
                self._client.aio.models.generate_content(model=model, contents=contents, config=config),
                timeout=_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001 — translated below
            code = getattr(exc, "code", 0) if isinstance(exc, genai_errors.APIError) else 0
            delay: float | None = None
            if code == 429:
                # Rate limits (free tier: 5 req/min) tell us when to come back;
                # honoring that is the difference between a slow job and a dead one.
                delay = min((_retry_delay_seconds(exc) or 30.0) + 1.0, _MAX_RETRY_SLEEP)
            elif code in (500, 502, 503) or isinstance(exc, asyncio.TimeoutError):
                delay = 1.5
            if attempts_left > 0 and delay is not None:
                log.info("gemini transient (%s); retrying in %.1fs", code or "timeout", delay)
                await asyncio.sleep(delay)
                return await self._generate(
                    contents, schema=schema, lite=lite, attempts_left=attempts_left - 1
                )
            log.warning("gemini call failed: %s", exc)
            raise self._translate_error(exc) from exc

        if schema is not None:
            parsed = resp.parsed
            if parsed is None:
                # Schema enforcement nearly always succeeds; fall back to manual parse.
                try:
                    parsed = schema.model_validate_json(resp.text or "")
                except Exception as exc:
                    raise AIError("The AI returned an unreadable result. Try again.", byok=self._byok) from exc
            return parsed
        text = resp.text
        if not text:
            raise AIError("The AI returned an empty result (possibly a safety block).", byok=self._byok)
        return text.strip()

    # -- protocol ----------------------------------------------------------------
    async def analyze(self, jd: str, cv_text: str, language: str) -> JobAnalysis:
        return await self._generate(prompts.analyze_prompt(jd, cv_text), schema=JobAnalysis)

    async def parse_cv(self, raw_text: str | None, pdf_bytes: bytes | None, language: str) -> CVData:
        if pdf_bytes is not None:
            contents = [
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                prompts.parse_cv_prompt(language),
            ]
        else:
            contents = prompts.parse_cv_prompt(language) + "\n\nCV TEXT:\n" + (raw_text or "")
        return await self._generate(contents, schema=CVData)

    async def tailor_cv(self, jd: str, analysis: JobAnalysis, master: CVData, language: str) -> CVData:
        keywords = [k.term for k in analysis.keywords]
        prompt = prompts.tailor_cv_prompt(
            jd, analysis.notes, keywords, master.model_dump_json(indent=1), language
        )
        tailored: CVData = await self._generate(prompt, schema=CVData)
        # Contacts and identity are not the model's to change.
        tailored.full_name = master.full_name or tailored.full_name
        tailored.contacts = master.contacts
        return tailored

    async def write_letter(self, jd: str, analysis: JobAnalysis, cv: CVData, language: str) -> LetterData:
        prompt = prompts.letter_prompt(jd, analysis.notes, cv.model_dump_json(indent=1), language)
        letter: LetterData = await self._generate(prompt, schema=LetterData)
        return letter

    async def outreach(self, jd: str, analysis: JobAnalysis, cv: CVData, language: str) -> str:
        return await self._generate(prompts.outreach_prompt(jd, cv.model_dump_json(), language))

    async def edit_cv_data(self, cv: CVData, instruction: str, language: str) -> CVData:
        prompt = prompts.edit_cv_prompt(cv.model_dump_json(indent=1), instruction, language)
        return await self._generate(prompt, schema=CVData)

    async def edit_letter_data(self, letter: LetterData, instruction: str, language: str) -> LetterData:
        prompt = prompts.edit_letter_prompt(letter.model_dump_json(indent=1), instruction, language)
        return await self._generate(prompt, schema=LetterData)

    async def edit_source(self, source: str, instruction: str) -> str:
        text: str = await self._generate(prompts.edit_source_prompt(source, instruction))
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
        return text.strip() + "\n"

    async def validate_key(self) -> bool:
        try:
            await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._model_lite,
                    contents="ping",
                    config=types.GenerateContentConfig(max_output_tokens=1),
                ),
                timeout=15,
            )
            return True
        except Exception:
            return False


def _json_dump(model: BaseModel) -> str:
    return json.dumps(model.model_dump(), ensure_ascii=False)
