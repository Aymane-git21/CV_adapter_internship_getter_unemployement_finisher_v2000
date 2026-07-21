"""LLM layer for the bench.

Unlike the product (schema-enforced JSON), this bench compares AI-AUTHORED
MARKUP, so calls are free-form text. Retry/backoff mirrors
backend/app/ai/gemini.py: honor the server-suggested delay on 429, short
retry on 5xx/timeout. FakeLLM plays back scripted responses for offline
tests of the harness itself.
"""
import asyncio
import re
import time

from google import genai
from google.genai import errors as genai_errors

_TIMEOUT = 120
_MAX_RETRY_SLEEP = 65.0
_RETRY_DELAY = re.compile(r"retry(?:Delay'?:\s*'|\s+in\s+)([\d.]+)s", re.IGNORECASE)


def strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1 :] if nl != -1 else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip() + "\n"


class LiveLLM:
    """Same model + retry discipline as the production provider."""

    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.calls = 0

    async def generate(self, prompt: str) -> tuple[str, int]:
        """Return (source_text, elapsed_ms). Raises on non-retryable failure."""
        attempts_left = 2
        while True:
            t0 = time.perf_counter()
            try:
                resp = await asyncio.wait_for(
                    self._client.aio.models.generate_content(model=self.model, contents=prompt),
                    timeout=_TIMEOUT,
                )
            except Exception as exc:  # noqa: BLE001 — classified below
                code = getattr(exc, "code", 0) if isinstance(exc, genai_errors.APIError) else 0
                delay = None
                if code == 429:
                    m = _RETRY_DELAY.search(str(exc))
                    delay = min((float(m.group(1)) if m else 30.0) + 1.0, _MAX_RETRY_SLEEP)
                elif code in (500, 502, 503) or isinstance(exc, asyncio.TimeoutError):
                    delay = 2.0
                if attempts_left > 0 and delay is not None:
                    attempts_left -= 1
                    await asyncio.sleep(delay)
                    continue
                raise
            self.calls += 1
            text = (resp.text or "").strip()
            if not text:
                raise RuntimeError("empty LLM response (safety block?)")
            return strip_fences(text), int((time.perf_counter() - t0) * 1000)


class FakeLLM:
    """Plays back scripted responses in order; records every prompt."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.prompts: list[str] = []
        self.calls = 0
        self.model = "fake"

    async def generate(self, prompt: str) -> tuple[str, int]:
        self.prompts.append(prompt)
        self.calls += 1
        if not self._responses:
            raise RuntimeError("FakeLLM ran out of scripted responses")
        return strip_fences(self._responses.pop(0)), 1
