"""Gemini provider — modern google-genai SDK, async, schema-enforced output."""
import asyncio
import json
import logging
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


class GeminiProvider:
    def __init__(self, api_key: str):
        self._byok = api_key != get_settings().gemini_api_key
        self._client = genai.Client(api_key=api_key)
        self._model = get_settings().gemini_model
        self._model_lite = get_settings().gemini_model_lite

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
                    "Your Gemini API key hit its rate/quota limit — wait a minute or check your plan."
                    if self._byok
                    else "The AI service is at capacity right now. Try again shortly."
                )
                return AIError(msg, byok=self._byok)
            return AIError(f"AI service error ({code}). Try again shortly.", byok=self._byok)
        if isinstance(exc, asyncio.TimeoutError):
            return AIError("The AI took too long to respond. Try again.", byok=self._byok)
        return AIError("Unexpected AI failure. Try again.", byok=self._byok)

    async def _generate(self, contents, *, schema: type[T] | None = None, lite: bool = False, retry: bool = True):
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
            transient = code in (429, 500, 502, 503)
            if retry and (transient or isinstance(exc, asyncio.TimeoutError)):
                # 429s need a longer breather than blips; one retry either way.
                await asyncio.sleep(3.0 if code == 429 else 1.5)
                return await self._generate(contents, schema=schema, lite=lite, retry=False)
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
