---
name: gemini-api
description: Using the Google Gemini API correctly in CV Glowup — the modern google-genai SDK (NOT the deprecated google-generativeai package the legacy code uses), async clients, structured JSON output, streaming, native PDF input, and BYO-API-key handling. Use when touching any AI generation code.
---

# Gemini API (CV Glowup)

## SDK migration — first thing to know

The legacy code (`app.py`, `run_adaptation.py`) uses `google.generativeai` (`genai.configure(...)`, `genai.GenerativeModel(...)`). That SDK is **deprecated/EOL — do not write new code with it**. Use the `google-genai` package:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=key)                      # per-request client is cheap; build one per user key
resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)

# async (preferred in the FastAPI backend):
resp = await client.aio.models.generate_content(model="gemini-2.5-flash", contents=prompt)
```

`requirements.txt`: replace `google-generativeai` with `google-genai`. The old `transport="rest"` / GRPC env-var workarounds at the top of app.py become unnecessary — delete them.

If anything here disagrees with current docs at ai.google.dev, the docs win — verify before debugging mysterious SDK errors.

## Structured output — never regex-parse JSON again

The legacy `extract_json()`/`clean_markdown()` regex scraping is replaced by schema-enforced output:

```python
from pydantic import BaseModel

class AtsAnalysis(BaseModel):
    job_title: str
    company: str
    ats_score: int
    missing_keywords: list[str]
    cv_improvements: str

resp = await client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=AtsAnalysis,
    ),
)
analysis = resp.parsed  # an AtsAnalysis instance
```

All generation steps (ATS analysis, CVData, CoverLetterData, outreach message) return pydantic models. The CV/CL schemas are the same ones the Typst renderer consumes (see typst-doc-engine skill).

## Native PDF input — replace pypdf text scraping

Don't extract text with pypdf (loses layout/structure). Hand Gemini the PDF directly:

```python
contents=[
    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
    "Extract this CV into the CVData schema...",
]
```

## Streaming (for the live editor experience)

```python
async for chunk in await client.aio.models.generate_content_stream(model=..., contents=...):
    yield chunk.text   # pipe into the SSE channel
```

Stream the cover-letter body and chat-edit responses; structured-output steps complete fast enough to skip streaming.

## Model selection

- `gemini-2.5-flash` — default workhorse (generation, chat edits).
- `gemini-2.5-flash-lite` — ATS analysis / extraction steps where quality tolerance allows; cheaper for free-tier traffic.
- `gemini-2.5-pro` — optional "priority writing" for top paid tier.
Centralize model ids in config — never hardcode in call sites.

## BYO API key rules

- The user's key lives in their browser (localStorage), is sent per request over HTTPS in a header (`X-User-Gemini-Key`), used to build a transient `genai.Client`, and is **never persisted, logged, or echoed in errors**.
- Validate on entry with the cheapest possible call (e.g. a 1-token `generate_content` on flash-lite or a `models.list`), return clear invalid/quota errors.
- Catch 429/RESOURCE_EXHAUSTED from user keys and surface as "your key's quota" — distinct from platform quota errors.
- Per-user concurrency caps still apply on BYO traffic (protects our infra, not their wallet).

## Error handling & retries

Wrap calls with: timeout (60 s generation, 10 s validation), retry once on 5xx/transient with jitter, no retry on 4xx. On safety blocks (`resp.candidates[0].finish_reason`), return an actionable message rather than a stack trace.
