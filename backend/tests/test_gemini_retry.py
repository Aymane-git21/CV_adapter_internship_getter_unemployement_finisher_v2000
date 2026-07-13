"""Gemini 429 handling: parse Google's server-suggested backoff and retry.

Root cause this guards: the shared server key is free tier (5 requests/min
for gemini-3.5-flash); one generation is exactly 5 calls, so bursts trip the
limit. Google's 429 carries RetryInfo (~30s); sleeping a fixed 3s guaranteed
the retry failed inside the same window and killed the job.
"""
import asyncio
from types import SimpleNamespace

from google.genai import errors as genai_errors

from backend.app.ai.gemini import GeminiProvider, _retry_delay_seconds

# Trimmed from a real production log line (2026-07-13).
_REAL_429_TEXT = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your "
    "current quota... Please retry in 28.343756161s.', 'status': 'RESOURCE_EXHAUSTED', "
    "'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', "
    "'retryDelay': '28s'}]}}"
)


class _Fake429(genai_errors.APIError):
    def __init__(self, text=_REAL_429_TEXT):
        Exception.__init__(self, text)
        self._text = text
        self.code = 429

    def __str__(self):
        return self._text


def test_retry_delay_parses_retryinfo_detail():
    assert _retry_delay_seconds(_Fake429("... 'retryDelay': '33.927396146s' ...")) == 33.927396146


def test_retry_delay_parses_prose_hint():
    assert _retry_delay_seconds(_Fake429("Please retry in 28.343756161s.")) == 28.343756161


def test_retry_delay_none_without_hint():
    assert _retry_delay_seconds(_Fake429("429 no hint here")) is None


async def test_429_retries_with_server_delay(monkeypatch):
    provider = GeminiProvider(api_key="test-key-not-used")

    calls = {"n": 0}

    async def fake_generate_content(model, contents, config):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _Fake429()
        return SimpleNamespace(text="ok", parsed=None)

    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr(provider._client.aio.models, "generate_content", fake_generate_content)
    monkeypatch.setattr("backend.app.ai.gemini.asyncio.sleep", fake_sleep)

    result = await provider._generate("ping")
    assert result == "ok"
    assert calls["n"] == 3
    # Both waits honored the server's ~28s hint (+1s cushion), not a fixed 3s.
    assert sleeps == [29.343756161, 29.343756161]


async def test_429_gives_up_after_retries(monkeypatch):
    from backend.app.ai.base import AIError

    provider = GeminiProvider(api_key="test-key-not-used")

    async def always_429(model, contents, config):
        raise _Fake429()

    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(provider._client.aio.models, "generate_content", always_429)
    monkeypatch.setattr("backend.app.ai.gemini.asyncio.sleep", instant_sleep)

    try:
        await provider._generate("ping")
        raise AssertionError("expected AIError")
    except AIError:
        pass
