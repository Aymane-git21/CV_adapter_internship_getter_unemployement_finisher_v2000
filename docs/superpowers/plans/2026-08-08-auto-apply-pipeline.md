# Auto-Apply Pipeline (Phases 1+2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Postings for a saved search (Toulouse, France first) arrive automatically, get tailored documents plus screening answers on demand, and go out as email applications from a review queue with one approval click.

**Architecture:** New `sources/` adapters (France Travail, Adzuna) normalize into one `JobPostingIn` contract and an ingest service dedupes into `job_postings` + per-user `applications` rows with a strict state machine (`inbox → generated → approved → sent → replied|rejected`). Generation reuses the existing `jobs.py` pipeline and adds a fourth `answers` document for pipeline-originated jobs. Sending builds a MIME email (outreach message as body, CV + letter PDFs attached) and ships it via the user's own Gmail (OAuth `gmail.send`) or a `.eml` file fallback in dev.

**Tech Stack:** FastAPI + SQLAlchemy async + SQLite/Postgres (existing), httpx (already a dependency) for source APIs and Gmail REST, google-genai provider abstraction (existing, incl. offline fake), React + react-router (existing frontend).

**Spec:** `docs/superpowers/specs/2026-08-08-auto-apply-design.md`

## Global Constraints

- Review queue only: every send is individually approved; no unattended submissions.
- No third-party platform passwords collected or stored, ever.
- No server-side scraping; server code talks only to official APIs (France Travail, Adzuna, Gmail).
- Email sends from the user's own Gmail via OAuth `gmail.send`, never from a cvglowup.com address; dev fallback writes `.eml` files.
- Hard per-day send cap, default 15 (`send_cap_daily` setting).
- Schema changes to existing tables go through `_ensure_columns` in `backend/app/db.py`; new tables via `create_all`.
- Everything must work offline with `CVG_FAKE_AI=1` (tests never hit live HTTP: use `httpx.MockTransport`).
- Gate tests live in `backend/tests/`, run with `python -m pytest backend/tests/<file> -v` from the repo root, deterministic, no network.
- All user-facing strings go through `frontend/src/i18n.tsx` in en, fr, and de.
- France Travail endpoint URLs are best-known constants; confirm against live docs during Task 4 (open item from the spec) — the adapter's shape does not change.
- Async test style: before writing any async test, open `backend/tests/test_api.py` and copy its exact marker/fixture convention (`@pytest.mark.anyio` vs asyncio auto-mode). The test code in this plan uses `@pytest.mark.anyio`; drop or swap the marker to match the repo if it differs.

---

### Task 1: Contract schemas, tables, and per-user columns

**Files:**
- Modify: `backend/app/schemas.py` (append at end)
- Modify: `backend/app/models.py` (append at end)
- Modify: `backend/app/db.py:41-48` (`_ensure_columns`)
- Test: `backend/tests/test_pipeline_models.py`

**Interfaces:**
- Produces: `JobPostingIn`, `FactsProfile`, `AnswerItem`, `AnswersDoc`, `SavedSearchParams` (pydantic); `SavedSearch`, `JobPosting`, `Application` (SQLAlchemy); `users.facts` JSON column, `users.pipeline_enabled` bool-int column, `users.gmail_refresh_token` text column.
- Consumes: `Base`, `utcnow` from existing modules.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_models.py`:

```python
"""Tables and contracts for the auto-apply pipeline."""
import pytest
from sqlalchemy import select

from backend.app.db import session_factory
from backend.app.models import Application, JobPosting, SavedSearch, User
from backend.app.schemas import AnswersDoc, FactsProfile, JobPostingIn
from backend.tests.conftest import unique_email


def test_job_posting_in_defaults():
    p = JobPostingIn(source="ft", external_id="123", title="Dev Python", description="d" * 100)
    assert p.company == ""
    assert p.apply_email is None
    assert p.apply_url is None
    assert p.raw == {}


def test_facts_profile_defaults():
    f = FactsProfile()
    assert f.work_permit == ""
    assert f.notice_period == ""
    assert f.salary_range == ""
    assert AnswersDoc().items == []


@pytest.mark.anyio
async def test_pipeline_tables_roundtrip(client):
    async with session_factory()() as db:
        user = User(email=unique_email())
        db.add(user)
        await db.flush()
        search = SavedSearch(user_id=user.id, name="Toulouse ML", keywords="machine learning",
                             insee="31555", radius_km=20)
        db.add(search)
        await db.flush()
        posting = JobPosting(source="ft", external_id="FT-1", title="ML Engineer",
                             company="Lumina", description="desc", fuzzy_hash="abc")
        db.add(posting)
        await db.flush()
        app_row = Application(user_id=user.id, posting_id=posting.id)
        db.add(app_row)
        await db.commit()

        got = (await db.execute(select(Application).where(Application.user_id == user.id))).scalar_one()
        assert got.status == "inbox"
        assert got.audit == []
        # user columns added by _ensure_columns
        assert user.facts is None
        assert user.pipeline_enabled == 0
        assert user.gmail_refresh_token is None


@pytest.mark.anyio
async def test_posting_unique_per_source(client):
    from sqlalchemy.exc import IntegrityError
    async with session_factory()() as db:
        db.add(JobPosting(source="ft", external_id="DUP", title="A", description="x", fuzzy_hash="h1"))
        await db.commit()
    async with session_factory()() as db:
        db.add(JobPosting(source="ft", external_id="DUP", title="B", description="y", fuzzy_hash="h2"))
        with pytest.raises(IntegrityError):
            await db.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'Application'`

- [ ] **Step 3: Implement schemas**

Append to `backend/app/schemas.py`:

```python
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
```

- [ ] **Step 4: Implement models**

Append to `backend/app/models.py`:

```python
class SavedSearch(Base):
    """One polled query, e.g. 'machine learning' around Toulouse."""

    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="Search")
    keywords: Mapped[str] = mapped_column(String(255), default="")
    insee: Mapped[str] = mapped_column(String(12), default="")
    radius_km: Mapped[int] = mapped_column(Integer, default=20)
    contract_type: Mapped[str] = mapped_column(String(32), default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobPosting(Base):
    """A posting fetched from a source. Global, shared across users."""

    __tablename__ = "job_postings"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_posting_source_ext"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(24), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    contract_type: Mapped[str] = mapped_column(String(32), default="")
    description: Mapped[str] = mapped_column(Text)
    apply_email: Mapped[str | None] = mapped_column(String(255), default=None)
    apply_url: Mapped[str | None] = mapped_column(Text, default=None)
    posted_at: Mapped[str] = mapped_column(String(40), default="")
    fuzzy_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Application(Base):
    """One user's pursuit of one posting; the review-queue row."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "posting_id", name="uq_application_user_posting"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), default=None)
    status: Mapped[str] = mapped_column(String(16), default="inbox")
    audit: Mapped[list] = mapped_column(JSON, default=list)
    sent_via: Mapped[str | None] = mapped_column(String(16), default=None)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
```

Add three columns to `User` (after `gens_date`, before `created_at`):

```python
    facts: Mapped[dict | None] = mapped_column(JSON, default=None)  # FactsProfile
    pipeline_enabled: Mapped[int] = mapped_column(Integer, default=0)  # feature flag
    gmail_refresh_token: Mapped[str | None] = mapped_column(Text, default=None)
```

- [ ] **Step 5: Extend `_ensure_columns`**

In `backend/app/db.py`, replace the body of `_ensure_columns` with:

```python
def _ensure_columns(conn) -> None:
    """Minimal in-place migration: create_all only creates missing tables, so
    columns added to existing tables are ALTERed here (SQLite and Postgres)."""
    from sqlalchemy import inspect, text

    cols = {c["name"] for c in inspect(conn).get_columns("jobs")}
    if "gen_params" not in cols:
        conn.execute(text("ALTER TABLE jobs ADD COLUMN gen_params JSON"))

    ucols = {c["name"] for c in inspect(conn).get_columns("users")}
    if "facts" not in ucols:
        conn.execute(text("ALTER TABLE users ADD COLUMN facts JSON"))
    if "pipeline_enabled" not in ucols:
        conn.execute(text("ALTER TABLE users ADD COLUMN pipeline_enabled INTEGER DEFAULT 0"))
    if "gmail_refresh_token" not in ucols:
        conn.execute(text("ALTER TABLE users ADD COLUMN gmail_refresh_token TEXT"))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_pipeline_models.py -v`
Expected: 4 PASS

Run the full gate to catch regressions: `python -m pytest backend/tests -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/models.py backend/app/db.py backend/tests/test_pipeline_models.py
git commit -m "feat(pipeline): posting/application tables, contracts, user columns"
```

---

### Task 2: Application state machine

**Files:**
- Create: `backend/app/pipeline_states.py`
- Test: `backend/tests/test_pipeline_states.py`

**Interfaces:**
- Produces: `ALLOWED: dict[str, set[str]]`, `advance(application, to: str, note: str = "") -> None` (mutates `status`, appends to `audit`, raises `ValueError` on illegal transition), `TERMINAL: set[str]`.
- Consumes: `Application` model from Task 1 (only `.status` and `.audit` attributes; works on any object having them).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_states.py`:

```python
"""Review-queue state machine: inbox → generated → approved → sent → replied|rejected."""
import pytest

from backend.app.pipeline_states import ALLOWED, TERMINAL, advance


class FakeApp:
    def __init__(self, status="inbox"):
        self.status = status
        self.audit = []


def test_happy_path():
    a = FakeApp()
    for to in ("generated", "approved", "sent", "replied"):
        advance(a, to)
    assert a.status == "replied"
    assert [e["to"] for e in a.audit] == ["generated", "approved", "sent", "replied"]
    assert all("ts" in e and "from" in e for e in a.audit)


def test_reject_allowed_from_any_non_terminal():
    for start in ("inbox", "generated", "approved", "sent"):
        a = FakeApp(start)
        advance(a, "rejected", note="not a fit")
        assert a.status == "rejected"
        assert a.audit[-1]["note"] == "not a fit"


def test_illegal_transitions_raise():
    with pytest.raises(ValueError):
        advance(FakeApp("inbox"), "sent")
    with pytest.raises(ValueError):
        advance(FakeApp("sent"), "approved")
    with pytest.raises(ValueError):
        advance(FakeApp("replied"), "rejected")  # terminal


def test_terminal_set():
    assert TERMINAL == {"replied", "rejected"}
    assert set(ALLOWED) == {"inbox", "generated", "approved", "sent", "replied", "rejected"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_states.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.pipeline_states'`

- [ ] **Step 3: Implement**

Create `backend/app/pipeline_states.py`:

```python
"""Review-queue state machine. The audit trail is append-only; every
transition is recorded with a timestamp so 'what happened to this
application' is always answerable from the row alone."""
from datetime import UTC, datetime

TERMINAL: set[str] = {"replied", "rejected"}

ALLOWED: dict[str, set[str]] = {
    "inbox": {"generated", "rejected"},
    "generated": {"approved", "rejected"},
    "approved": {"sent", "rejected"},
    "sent": {"replied", "rejected"},
    "replied": set(),
    "rejected": set(),
}


def advance(application, to: str, note: str = "") -> None:
    """Move `application` to state `to`, or raise ValueError."""
    frm = application.status
    if to not in ALLOWED.get(frm, set()):
        raise ValueError(f"Illegal transition {frm} -> {to}")
    application.status = to
    entries = list(application.audit or [])
    entries.append(
        {"ts": datetime.now(UTC).isoformat(), "from": frm, "to": to, "note": note}
    )
    application.audit = entries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_pipeline_states.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline_states.py backend/tests/test_pipeline_states.py
git commit -m "feat(pipeline): application state machine with audit trail"
```

---

### Task 3: Source adapter protocol and registry

**Files:**
- Create: `backend/app/sources/__init__.py`
- Test: `backend/tests/test_pipeline_sources.py`

**Interfaces:**
- Produces: `SourceAdapter` (Protocol with `name: str` and `async fetch(params: SavedSearchParams, client: httpx.AsyncClient) -> list[JobPostingIn]`), `register(adapter) -> None`, `get_source(name) -> SourceAdapter`, `all_sources() -> list[SourceAdapter]`, `SourceError(Exception)`.
- Consumes: `SavedSearchParams`, `JobPostingIn` from Task 1.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_sources.py`:

```python
"""Adapter registry. Concrete adapter tests live in their own files."""
import httpx
import pytest

from backend.app.schemas import JobPostingIn, SavedSearchParams
from backend.app.sources import SourceError, all_sources, get_source, register


class DummySource:
    name = "dummy"

    async def fetch(self, params: SavedSearchParams, client: httpx.AsyncClient):
        return [JobPostingIn(source=self.name, external_id="1", title="T", description="D")]


def test_register_and_get():
    register(DummySource())
    assert get_source("dummy").name == "dummy"
    assert any(s.name == "dummy" for s in all_sources())


def test_get_unknown_raises():
    with pytest.raises(SourceError):
        get_source("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_sources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.sources'`

- [ ] **Step 3: Implement**

Create `backend/app/sources/__init__.py`:

```python
"""Job-posting source adapters. Every adapter normalizes into JobPostingIn;
nothing downstream knows which board a posting came from. Server-side code
talks ONLY to official APIs — scraping bot-defended boards is out of scope
by design (see docs/superpowers/specs/2026-08-08-auto-apply-design.md)."""
from typing import Protocol

import httpx

from ..schemas import JobPostingIn, SavedSearchParams


class SourceError(Exception):
    """A source failed or is unknown; the poll survives and reports it."""


class SourceAdapter(Protocol):
    name: str

    async def fetch(
        self, params: SavedSearchParams, client: httpx.AsyncClient
    ) -> list[JobPostingIn]: ...


_REGISTRY: dict[str, SourceAdapter] = {}


def register(adapter: SourceAdapter) -> None:
    _REGISTRY[adapter.name] = adapter


def get_source(name: str) -> SourceAdapter:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise SourceError(f"Unknown source '{name}'") from exc


def all_sources() -> list[SourceAdapter]:
    return list(_REGISTRY.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_pipeline_sources.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/sources/__init__.py backend/tests/test_pipeline_sources.py
git commit -m "feat(pipeline): source adapter protocol and registry"
```

---

### Task 4: France Travail adapter

**Files:**
- Create: `backend/app/sources/france_travail.py`
- Create: `backend/tests/fixtures/france_travail_search.json`
- Modify: `backend/app/config.py` (add `ft_client_id: str = ""`, `ft_client_secret: str = ""` after the `adsense_client` line)
- Test: `backend/tests/test_source_france_travail.py`

**Interfaces:**
- Produces: `FranceTravailSource` with `name = "ft"`; module-level `TOKEN_URL`, `SEARCH_URL` constants. Registered in `backend/app/sources/__init__.py` at the bottom via `from . import france_travail  # noqa` in a later task (Task 7 wires registration on startup; here the class self-registers on import).
- Consumes: `SourceAdapter` protocol, `SavedSearchParams`, `JobPostingIn`, `SourceError` from Task 3; `get_settings()` for credentials.

> Open item from the spec, resolved here as constants to confirm at kickoff against live docs: token endpoint and search endpoint below are the documented France Travail (francetravail.io) values. If they changed, only the two constants change.

- [ ] **Step 1: Create the recorded fixture**

Create `backend/tests/fixtures/france_travail_search.json` (shape of `GET .../v2/offres/search` response, two offers, one with an application email, one with an external URL):

```json
{
  "resultats": [
    {
      "id": "185XKPT",
      "intitule": "Ingénieur Machine Learning (H/F)",
      "description": "Au sein de l'équipe data de Lumina AI à Toulouse, vous concevez des pipelines RAG en python avec pytorch et docker sur GCP.",
      "dateCreation": "2026-08-06T08:12:00.000Z",
      "lieuTravail": { "libelle": "31 - TOULOUSE", "commune": "31555" },
      "entreprise": { "nom": "LUMINA AI" },
      "typeContrat": "CDI",
      "contact": { "courriel": "recrutement@lumina.example" },
      "origineOffre": { "urlOrigine": "https://candidat.francetravail.fr/offres/recherche/detail/185XKPT" }
    },
    {
      "id": "185ZQRD",
      "intitule": "Data Engineer (H/F)",
      "description": "Chez Aerotech Toulouse vous industrialisez des flux de données avec airflow et kubernetes.",
      "dateCreation": "2026-08-05T14:03:00.000Z",
      "lieuTravail": { "libelle": "31 - TOULOUSE", "commune": "31555" },
      "entreprise": { "nom": "AEROTECH" },
      "typeContrat": "CDD",
      "contact": {},
      "origineOffre": { "urlOrigine": "https://aerotech.example/careers/data-engineer" }
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_source_france_travail.py`:

```python
"""France Travail adapter against recorded fixtures (no live HTTP)."""
import json
from pathlib import Path

import httpx
import pytest

from backend.app.schemas import SavedSearchParams
from backend.app.sources import SourceError
from backend.app.sources.france_travail import SEARCH_URL, TOKEN_URL, FranceTravailSource

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "france_travail_search.json").read_text(encoding="utf-8")
)


def _transport(search_status=200, search_json=None):
    calls = {"token": 0, "search": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(TOKEN_URL):
            calls["token"] += 1
            assert request.method == "POST"
            body = request.content.decode()
            assert "client_credentials" in body and "api_offresdemploiv2" in body
            return httpx.Response(200, json={"access_token": "tok-123", "expires_in": 1499})
        calls["search"] += 1
        assert request.headers["Authorization"] == "Bearer tok-123"
        params = dict(request.url.params)
        assert params["motsCles"] == "machine learning"
        assert params["commune"] == "31555"
        assert params["distance"] == "20"
        return httpx.Response(search_status, json=search_json if search_json is not None else FIXTURE)

    return httpx.MockTransport(handler), calls


@pytest.mark.anyio
async def test_fetch_normalizes_offers():
    transport, calls = _transport()
    src = FranceTravailSource(client_id="cid", client_secret="sec")
    async with httpx.AsyncClient(transport=transport) as client:
        postings = await src.fetch(
            SavedSearchParams(keywords="machine learning", insee="31555", radius_km=20), client
        )
    assert calls == {"token": 1, "search": 1}
    assert len(postings) == 2
    first = postings[0]
    assert first.source == "ft"
    assert first.external_id == "185XKPT"
    assert first.title == "Ingénieur Machine Learning (H/F)"
    assert first.company == "LUMINA AI"
    assert first.location == "31 - TOULOUSE"
    assert first.contract_type == "CDI"
    assert first.apply_email == "recrutement@lumina.example"
    second = postings[1]
    assert second.apply_email is None
    assert second.apply_url == "https://aerotech.example/careers/data-engineer"


@pytest.mark.anyio
async def test_search_failure_raises_source_error():
    transport, _ = _transport(search_status=500, search_json={"error": "boom"})
    src = FranceTravailSource(client_id="cid", client_secret="sec")
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(SourceError):
            await src.fetch(SavedSearchParams(keywords="machine learning", insee="31555"), client)


@pytest.mark.anyio
async def test_missing_credentials_raise_before_any_call():
    src = FranceTravailSource(client_id="", client_secret="")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as client:
        with pytest.raises(SourceError):
            await src.fetch(SavedSearchParams(keywords="x"), client)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_source_france_travail.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.sources.france_travail'`

- [ ] **Step 4: Implement**

Create `backend/app/sources/france_travail.py`:

```python
"""France Travail (ex-Pôle emploi) Offres d'emploi v2 adapter.

Auth: OAuth2 client-credentials against the francetravail.io partner realm.
The token is cached on the instance and refreshed when expired. Endpoint
constants are the documented values; confirm at kickoff (spec open item)."""
import time

import httpx

from ..schemas import JobPostingIn, SavedSearchParams
from . import SourceError

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE = "api_offresdemploiv2 o2dsoffre"


class FranceTravailSource:
    name = "ft"

    def __init__(self, client_id: str, client_secret: str):
        self._id = client_id
        self._secret = client_secret
        self._token: str | None = None
        self._token_exp: float = 0.0

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.monotonic() < self._token_exp - 60:
            return self._token
        resp = await client.post(
            TOKEN_URL,
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": self._id,
                "client_secret": self._secret,
                "scope": SCOPE,
            },
        )
        if resp.status_code != 200:
            raise SourceError(f"France Travail token request failed ({resp.status_code})")
        body = resp.json()
        self._token = body["access_token"]
        self._token_exp = time.monotonic() + float(body.get("expires_in", 1200))
        return self._token

    async def fetch(
        self, params: SavedSearchParams, client: httpx.AsyncClient
    ) -> list[JobPostingIn]:
        if not self._id or not self._secret:
            raise SourceError("France Travail credentials are not configured (FT_CLIENT_ID/SECRET).")
        token = await self._ensure_token(client)
        query: dict[str, str] = {"motsCles": params.keywords}
        if params.insee:
            query["commune"] = params.insee
            query["distance"] = str(params.radius_km)
        if params.contract_type:
            query["typeContrat"] = params.contract_type
        resp = await client.get(SEARCH_URL, params=query, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 429:
            raise SourceError("France Travail rate limit hit; the next poll will retry.")
        if resp.status_code not in (200, 206):  # 206 = partial content, documented for paging
            raise SourceError(f"France Travail search failed ({resp.status_code})")
        out: list[JobPostingIn] = []
        for offer in resp.json().get("resultats", []):
            contact = offer.get("contact") or {}
            out.append(
                JobPostingIn(
                    source=self.name,
                    external_id=str(offer.get("id", "")),
                    title=offer.get("intitule", ""),
                    company=(offer.get("entreprise") or {}).get("nom", ""),
                    location=(offer.get("lieuTravail") or {}).get("libelle", ""),
                    contract_type=offer.get("typeContrat", ""),
                    description=offer.get("description", ""),
                    apply_email=contact.get("courriel") or None,
                    apply_url=(offer.get("origineOffre") or {}).get("urlOrigine") or None,
                    posted_at=offer.get("dateCreation", ""),
                    raw=offer,
                )
            )
        return out
```

The module only exports the class; instantiation with real credentials happens in Task 7's `build_sources()`. Delete the unused `register` import if your editor added one — this file imports only `SourceError` from the package.

Add to `backend/app/config.py` after `adsense_client: str = ""`:

```python
    # Auto-apply pipeline (Phase 1)
    ft_client_id: str = ""
    ft_client_secret: str = ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_source_france_travail.py backend/tests/test_config.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/sources/france_travail.py backend/tests/fixtures/france_travail_search.json backend/tests/test_source_france_travail.py backend/app/config.py
git commit -m "feat(pipeline): France Travail source adapter with fixture tests"
```

---

### Task 5: Adzuna adapter

**Files:**
- Create: `backend/app/sources/adzuna.py`
- Create: `backend/tests/fixtures/adzuna_search.json`
- Modify: `backend/app/config.py` (add `adzuna_app_id: str = ""`, `adzuna_app_key: str = ""` under the pipeline block from Task 4)
- Test: `backend/tests/test_source_adzuna.py`

**Interfaces:**
- Produces: `AdzunaSource` with `name = "adzuna"`, `SEARCH_URL` constant. Same `fetch` signature as Task 4.
- Consumes: Task 3 protocol and Task 1 schemas.

- [ ] **Step 1: Create the fixture**

Create `backend/tests/fixtures/adzuna_search.json`:

```json
{
  "results": [
    {
      "id": "5011223344",
      "title": "Développeur Python Toulouse",
      "description": "Startup toulousaine cherche développeur python, fastapi, docker.",
      "created": "2026-08-04T09:30:00Z",
      "company": { "display_name": "Softlab" },
      "location": { "display_name": "Toulouse, Haute-Garonne" },
      "contract_type": "permanent",
      "redirect_url": "https://www.adzuna.fr/land/ad/5011223344"
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_source_adzuna.py`:

```python
"""Adzuna FR adapter against recorded fixtures."""
import json
from pathlib import Path

import httpx
import pytest

from backend.app.schemas import SavedSearchParams
from backend.app.sources import SourceError
from backend.app.sources.adzuna import SEARCH_URL, AdzunaSource

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "adzuna_search.json").read_text(encoding="utf-8")
)


@pytest.mark.anyio
async def test_fetch_normalizes_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(SEARCH_URL)
        params = dict(request.url.params)
        assert params["app_id"] == "aid" and params["app_key"] == "akey"
        assert params["what"] == "python"
        assert params["where"] == "Toulouse"
        return httpx.Response(200, json=FIXTURE)

    src = AdzunaSource(app_id="aid", app_key="akey")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        postings = await src.fetch(SavedSearchParams(keywords="python", insee="31555"), client)
    assert len(postings) == 1
    p = postings[0]
    assert p.source == "adzuna"
    assert p.external_id == "5011223344"
    assert p.company == "Softlab"
    assert p.apply_email is None
    assert p.apply_url == "https://www.adzuna.fr/land/ad/5011223344"


@pytest.mark.anyio
async def test_error_status_raises():
    src = AdzunaSource(app_id="aid", app_key="akey")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(403, json={}))
    ) as client:
        with pytest.raises(SourceError):
            await src.fetch(SavedSearchParams(keywords="python"), client)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_source_adzuna.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.sources.adzuna'`

- [ ] **Step 4: Implement**

Create `backend/app/sources/adzuna.py`:

```python
"""Adzuna France search API adapter (backfill source). INSEE codes mean
nothing to Adzuna, so location falls back to the city name: Toulouse's
code maps to the literal string until saved searches carry a city label."""
import httpx

from ..schemas import JobPostingIn, SavedSearchParams
from . import SourceError

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/1"

_INSEE_TO_CITY = {"31555": "Toulouse"}


class AdzunaSource:
    name = "adzuna"

    def __init__(self, app_id: str, app_key: str):
        self._id = app_id
        self._key = app_key

    async def fetch(
        self, params: SavedSearchParams, client: httpx.AsyncClient
    ) -> list[JobPostingIn]:
        if not self._id or not self._key:
            raise SourceError("Adzuna credentials are not configured (ADZUNA_APP_ID/KEY).")
        query = {
            "app_id": self._id,
            "app_key": self._key,
            "what": params.keywords,
            "where": _INSEE_TO_CITY.get(params.insee, params.insee),
            "distance": str(params.radius_km),
            "results_per_page": "50",
            "content-type": "application/json",
        }
        resp = await client.get(SEARCH_URL, params=query)
        if resp.status_code != 200:
            raise SourceError(f"Adzuna search failed ({resp.status_code})")
        out: list[JobPostingIn] = []
        for item in resp.json().get("results", []):
            out.append(
                JobPostingIn(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("title", ""),
                    company=(item.get("company") or {}).get("display_name", ""),
                    location=(item.get("location") or {}).get("display_name", ""),
                    contract_type=item.get("contract_type", ""),
                    description=item.get("description", ""),
                    apply_email=None,  # Adzuna never exposes application emails
                    apply_url=item.get("redirect_url") or None,
                    posted_at=item.get("created", ""),
                    raw=item,
                )
            )
        return out
```

Add to `backend/app/config.py` under the pipeline block:

```python
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_source_adzuna.py -v`
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/sources/adzuna.py backend/tests/fixtures/adzuna_search.json backend/tests/test_source_adzuna.py backend/app/config.py
git commit -m "feat(pipeline): Adzuna FR backfill source adapter"
```

---

### Task 6: Ingest service with dedup

**Files:**
- Create: `backend/app/pipeline_ingest.py`
- Test: `backend/tests/test_pipeline_ingest.py`

**Interfaces:**
- Produces: `fuzzy_hash(title: str, company: str) -> str` (sha1 hex of normalized strings), `async ingest(db, user_id: int, postings: list[JobPostingIn]) -> int` (stores new postings, creates `Application(status="inbox")` rows, returns count of new applications; idempotent).
- Consumes: `JobPosting`, `Application` models (Task 1); `JobPostingIn` schema; `normalize` from `backend/app/ats.py` for string normalization.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_ingest.py`:

```python
"""Idempotent ingest: same poll twice = zero new rows; cross-source dupes collapse."""
import pytest
from sqlalchemy import func, select

from backend.app.db import session_factory
from backend.app.models import Application, JobPosting, User
from backend.app.pipeline_ingest import fuzzy_hash, ingest
from backend.app.schemas import JobPostingIn
from backend.tests.conftest import unique_email


def _posting(source="ft", ext="A1", title="ML Engineer", company="Lumina"):
    return JobPostingIn(source=source, external_id=ext, title=title, company=company,
                        description="desc long enough")


def test_fuzzy_hash_normalizes():
    assert fuzzy_hash("ML  Engineer (H/F)", "LUMINA") == fuzzy_hash("ml engineer h/f", "Lumina")
    assert fuzzy_hash("ML Engineer", "Lumina") != fuzzy_hash("Data Engineer", "Lumina")


@pytest.mark.anyio
async def test_ingest_idempotent(client):
    async with session_factory()() as db:
        user = User(email=unique_email())
        db.add(user)
        await db.commit()
        uid = user.id

    async with session_factory()() as db:
        n1 = await ingest(db, uid, [_posting(), _posting(ext="A2", title="Data Engineer")])
        await db.commit()
    async with session_factory()() as db:
        n2 = await ingest(db, uid, [_posting(), _posting(ext="A2", title="Data Engineer")])
        await db.commit()
        assert (n1, n2) == (2, 0)
        total = (await db.execute(select(func.count(Application.id)).where(Application.user_id == uid))).scalar_one()
        assert total == 2


@pytest.mark.anyio
async def test_cross_source_duplicate_collapses(client):
    async with session_factory()() as db:
        user = User(email=unique_email())
        db.add(user)
        await db.commit()
        uid = user.id

    async with session_factory()() as db:
        await ingest(db, uid, [_posting(source="ft", ext="F1")])
        await db.commit()
    async with session_factory()() as db:
        n = await ingest(db, uid, [_posting(source="adzuna", ext="Z9")])  # same title+company
        await db.commit()
        # Posting stored (different source id) but NO second application for the user.
        assert n == 0
        postings = (await db.execute(select(func.count(JobPosting.id)))).scalar_one()
        apps = (await db.execute(select(func.count(Application.id)).where(Application.user_id == uid))).scalar_one()
        assert postings >= 2 and apps == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.pipeline_ingest'`

- [ ] **Step 3: Implement**

Create `backend/app/pipeline_ingest.py`:

```python
"""Store fetched postings and open inbox applications, idempotently.

Two dedup layers:
1. (source, external_id) unique — the same offer re-polled is a no-op.
2. fuzzy (title, company) hash per user — the same job seen on a second
   board does not create a second inbox card.
"""
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ats import normalize
from .models import Application, JobPosting
from .schemas import JobPostingIn


def fuzzy_hash(title: str, company: str) -> str:
    key = normalize(title).strip() + "|" + normalize(company).strip()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


async def ingest(db: AsyncSession, user_id: int, postings: list[JobPostingIn]) -> int:
    new_applications = 0
    for p in postings:
        if not p.external_id or not p.title:
            continue
        existing = (
            await db.execute(
                select(JobPosting).where(
                    JobPosting.source == p.source, JobPosting.external_id == p.external_id
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = JobPosting(
                source=p.source, external_id=p.external_id, title=p.title,
                company=p.company, location=p.location, contract_type=p.contract_type,
                description=p.description, apply_email=p.apply_email, apply_url=p.apply_url,
                posted_at=p.posted_at, fuzzy_hash=fuzzy_hash(p.title, p.company), raw=p.raw,
            )
            db.add(existing)
            await db.flush()

        has_app = (
            await db.execute(
                select(Application.id)
                .join(JobPosting, Application.posting_id == JobPosting.id)
                .where(
                    Application.user_id == user_id,
                    JobPosting.fuzzy_hash == existing.fuzzy_hash,
                )
            )
        ).first()
        if has_app is None:
            db.add(Application(user_id=user_id, posting_id=existing.id))
            new_applications += 1
    return new_applications
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_pipeline_ingest.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline_ingest.py backend/tests/test_pipeline_ingest.py
git commit -m "feat(pipeline): idempotent ingest with two-layer dedup"
```

---

### Task 7: Poller and internal poll endpoint

**Files:**
- Create: `backend/app/poller.py`
- Modify: `backend/app/config.py` (add `poll_interval_minutes: int = 60`, `internal_token: str = ""` under the pipeline block)
- Modify: `backend/app/main.py:17` (import + include new router; lifespan starts the dev loop)
- Test: `backend/tests/test_pipeline_poller.py`

**Interfaces:**
- Produces: `build_sources() -> list[SourceAdapter]` (constructs FT + Adzuna from settings, skipping unconfigured ones), `async poll_once() -> dict` (`{"new": int, "errors": [str]}` — polls every enabled SavedSearch of every `pipeline_enabled` user), `async poll_loop()` (dev loop, sleeps `poll_interval_minutes`), FastAPI router `internal_router` with `POST /api/internal/poll` (guarded: `X-Internal-Token` header must equal `settings.internal_token`; 403 otherwise; in prod Cloud Scheduler carries the token).
- Consumes: Tasks 3-6 (`all_sources` not used — poller holds its own built list; `ingest`; adapters), `SavedSearch`, `User` models.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_poller.py`:

```python
"""poll_once fans a saved search across sources; the internal endpoint is token-guarded."""
import httpx
import pytest

from backend.app import poller
from backend.app.db import session_factory
from backend.app.models import SavedSearch, User
from backend.app.schemas import JobPostingIn, SavedSearchParams
from backend.tests.conftest import unique_email


class StubSource:
    def __init__(self, name, postings=None, error=None):
        self.name = name
        self._postings = postings or []
        self._error = error

    async def fetch(self, params: SavedSearchParams, client: httpx.AsyncClient):
        if self._error:
            raise self._error
        return self._postings


@pytest.mark.anyio
async def test_poll_once_ingests_and_survives_source_failure(client, monkeypatch):
    async with session_factory()() as db:
        user = User(email=unique_email(), pipeline_enabled=1)
        db.add(user)
        await db.flush()
        db.add(SavedSearch(user_id=user.id, name="ML", keywords="ml", insee="31555"))
        await db.commit()

    from backend.app.sources import SourceError
    good = StubSource("ft", postings=[
        JobPostingIn(source="ft", external_id="P1", title="ML Engineer", company="Lumina",
                     description="d"),
    ])
    bad = StubSource("adzuna", error=SourceError("adzuna down"))
    monkeypatch.setattr(poller, "build_sources", lambda: [good, bad])

    result = await poller.poll_once()
    assert result["new"] == 1
    assert result["errors"] == ["adzuna down"]

    # Second run: idempotent.
    result2 = await poller.poll_once()
    assert result2["new"] == 0


@pytest.mark.anyio
async def test_internal_poll_requires_token(client, monkeypatch):
    monkeypatch.setattr(poller, "build_sources", lambda: [])
    r = await client.post("/api/internal/poll")
    assert r.status_code == 403
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "internal_token", "sekrit", raising=False)
    r2 = await client.post("/api/internal/poll", headers={"X-Internal-Token": "sekrit"})
    assert r2.status_code == 200
    assert set(r2.json()) == {"new", "errors"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_poller.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.poller'`

- [ ] **Step 3: Implement**

Create `backend/app/poller.py`:

```python
"""Scheduled posting fetch. Dev: an asyncio loop started from lifespan.
Prod: Cloud Scheduler POSTs /api/internal/poll with the internal token.
A failing source never kills the poll; its error is reported and the
other sources still land."""
import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from .config import get_settings
from .db import session_factory
from .models import SavedSearch, User
from .pipeline_ingest import ingest
from .schemas import SavedSearchParams
from .sources import SourceAdapter
from .sources.adzuna import AdzunaSource
from .sources.france_travail import FranceTravailSource

log = logging.getLogger(__name__)

internal_router = APIRouter(prefix="/api/internal", tags=["internal"])


def build_sources() -> list[SourceAdapter]:
    s = get_settings()
    out: list[SourceAdapter] = []
    if s.ft_client_id and s.ft_client_secret:
        out.append(FranceTravailSource(s.ft_client_id, s.ft_client_secret))
    if s.adzuna_app_id and s.adzuna_app_key:
        out.append(AdzunaSource(s.adzuna_app_id, s.adzuna_app_key))
    return out


async def poll_once() -> dict:
    sources = build_sources()
    new_total = 0
    errors: list[str] = []
    async with session_factory()() as db:
        rows = (
            await db.execute(
                select(SavedSearch, User)
                .join(User, SavedSearch.user_id == User.id)
                .where(SavedSearch.enabled == True, User.pipeline_enabled == 1)  # noqa: E712
            )
        ).all()
        async with httpx.AsyncClient(timeout=30) as client:
            for search, user in rows:
                params = SavedSearchParams(
                    keywords=search.keywords, insee=search.insee,
                    radius_km=search.radius_km, contract_type=search.contract_type,
                )
                for source in sources:
                    try:
                        postings = await source.fetch(params, client)
                        new_total += await ingest(db, user.id, postings)
                    except Exception as exc:  # noqa: BLE001 — reported, poll continues
                        log.warning("source %s failed: %s", source.name, exc)
                        errors.append(str(exc))
        await db.commit()
    return {"new": new_total, "errors": errors}


async def poll_loop() -> None:
    interval = max(5, get_settings().poll_interval_minutes) * 60
    while True:
        try:
            result = await poll_once()
            log.info("poll: %s new, %s errors", result["new"], len(result["errors"]))
        except Exception:  # pragma: no cover — loop must survive anything
            log.exception("poll loop iteration failed")
        await asyncio.sleep(interval)


@internal_router.post("/poll")
async def internal_poll(request: Request) -> dict:
    token = get_settings().internal_token
    if not token or request.headers.get("X-Internal-Token") != token:
        raise HTTPException(status_code=403, detail="Forbidden.")
    return await poll_once()
```

Add to `backend/app/config.py` under the pipeline block:

```python
    poll_interval_minutes: int = 60
    internal_token: str = ""
```

In `backend/app/main.py`:
- Line 17: extend the import to `from .routers import account, auth, billing, cvs, documents, generate, latex, templates` and add below it `from . import poller as pipeline_poller`.
- In `create_app()` where the other routers are included (search for `app.include_router(generate.router)` further down the file), add `app.include_router(pipeline_poller.internal_router)`.
- In `lifespan`, after the reaper block, start the dev loop only when configured:

```python
    poll_task = None
    if not settings.is_prod and (settings.ft_client_id or settings.adzuna_app_id):
        import asyncio as _asyncio

        poll_task = _asyncio.create_task(pipeline_poller.poll_loop())
    yield
    if poll_task is not None:
        poll_task.cancel()
```

(The existing `yield` moves into this block; keep the reaper cancel beside the poll cancel.) In prod, Cloud Scheduler owns the cadence via the internal endpoint; the in-process loop stays dev-only.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_pipeline_poller.py -v`
Expected: 2 PASS

Run the full gate: `python -m pytest backend/tests -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/poller.py backend/app/config.py backend/app/main.py backend/tests/test_pipeline_poller.py
git commit -m "feat(pipeline): poller with dev loop and token-guarded internal endpoint"
```

---

### Task 8: Facts profile endpoints and deterministic answers

**Files:**
- Create: `backend/app/answers.py`
- Modify: `backend/app/routers/account.py` (add GET/PUT `/api/account/facts`)
- Test: `backend/tests/test_pipeline_answers.py`

**Interfaces:**
- Produces: `FIXED_QUESTIONS: dict[str, list[tuple[str, str]]]` keyed by language (`en`/`fr`/`de`), each tuple `(facts_field, question_text)`; `fixed_answers(facts: FactsProfile, language: str) -> list[AnswerItem]` (only fields with a non-empty value; `origin="facts"`); REST: `GET /api/account/facts -> FactsProfile`, `PUT /api/account/facts` accepting a `FactsProfile` body (auth required).
- Consumes: `FactsProfile`, `AnswerItem` (Task 1); `get_current_user` from `backend/app/security.py`; existing router pattern in `backend/app/routers/account.py`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_answers.py`:

```python
"""Deterministic answers come from the facts profile, never the model."""
import pytest

from backend.app.answers import FIXED_QUESTIONS, fixed_answers
from backend.app.schemas import FactsProfile
from backend.tests.conftest import unique_email


def test_fixed_answers_only_filled_fields_and_language():
    facts = FactsProfile(work_permit="EU citizen", notice_period="1 month")
    en = fixed_answers(facts, "en")
    assert [a.origin for a in en] == ["facts", "facts"]
    assert any("work" in a.question.lower() for a in en)
    fr = fixed_answers(facts, "fr")
    assert len(fr) == 2 and fr[0].question != en[0].question
    assert fixed_answers(FactsProfile(), "en") == []
    assert set(FIXED_QUESTIONS) == {"en", "fr", "de"}


@pytest.mark.anyio
async def test_facts_roundtrip_via_api(client):
    email, password = unique_email(), "password123"
    await client.post("/api/auth/register", json={"email": email, "password": password})
    r = await client.get("/api/account/facts")
    assert r.status_code == 200
    assert r.json()["work_permit"] == ""
    r2 = await client.put("/api/account/facts", json={"work_permit": "EU citizen", "salary_range": "45-55k EUR"})
    assert r2.status_code == 200
    r3 = await client.get("/api/account/facts")
    assert r3.json()["work_permit"] == "EU citizen"
    assert r3.json()["salary_range"] == "45-55k EUR"


@pytest.mark.anyio
async def test_facts_require_auth(client):
    r = await client.get("/api/account/facts")
    assert r.status_code in (401, 403)
```

Note: the register call in `test_facts_roundtrip_via_api` sets the session cookie on the shared client (matches existing auth tests in `backend/tests/test_api.py`); `test_facts_require_auth` runs on a fresh `client` fixture instance so it is unauthenticated.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_answers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.answers'`

- [ ] **Step 3: Implement `answers.py`**

Create `backend/app/answers.py`:

```python
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
```

- [ ] **Step 4: Implement the facts endpoints**

In `backend/app/routers/account.py`, follow the file's existing imports/pattern (it already imports `get_current_user` and `get_db`; check the top of the file and reuse). Add:

```python
from ..schemas import FactsProfile


@router.get("/facts")
async def get_facts(user: Annotated[User, Depends(require_user)]) -> FactsProfile:
    return FactsProfile.model_validate(user.facts or {})


@router.put("/facts")
async def put_facts(
    body: FactsProfile,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> FactsProfile:
    user.facts = body.model_dump()
    await db.commit()
    return body
```

If `account.py` has no `require_user` dependency (only `get_current_user` returning `User | None`), define the guard inline at the top of the file once:

```python
async def require_user(user: Annotated[User | None, Depends(get_current_user)]) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Log in first.")
    return user
```

The account router's prefix is already `/api/account` (verify at the `APIRouter(prefix=...)` line and adjust the paths above if it differs — the tests pin the final URLs).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_pipeline_answers.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/answers.py backend/app/routers/account.py backend/tests/test_pipeline_answers.py
git commit -m "feat(pipeline): facts profile API and deterministic screening answers"
```

---

### Task 9: `write_answers` on the AI provider

**Files:**
- Modify: `backend/app/ai/base.py` (extend protocol)
- Modify: `backend/app/ai/prompts.py` (new prompt builder)
- Modify: `backend/app/ai/gemini.py` (implement)
- Modify: `backend/app/ai/fake.py` (implement deterministically)
- Test: `backend/tests/test_pipeline_answers_ai.py`

**Interfaces:**
- Produces: `AIProvider.write_answers(jd: str, analysis: JobAnalysis, master: CVData, facts: FactsProfile, language: str) -> AnswersDoc` — returns GENERATED items only (posting-specific questions); deterministic items are merged by the caller (Task 10). Every returned item has `origin="generated"`.
- Consumes: `AnswersDoc`, `AnswerItem`, `FactsProfile` (Task 1); existing `_generate(..., schema=...)` plumbing in `gemini.py`; existing prompt style in `prompts.py`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_answers_ai.py`:

```python
"""Provider contract for generated screening answers (offline fake)."""
import pytest

from backend.app.ai import get_provider
from backend.app.schemas import CVData, FactsProfile, JobAnalysis, Keyword


@pytest.mark.anyio
async def test_fake_write_answers_contract():
    provider = get_provider(None)  # CVG_FAKE_AI=1 in tests -> FakeProvider
    analysis = JobAnalysis(job_title="ML Engineer", company="Lumina",
                           keywords=[Keyword(term="python"), Keyword(term="docker")])
    master = CVData(full_name="Alex Martin", summary="ML engineer, 4 years")
    doc = await provider.write_answers("We need python and docker.", analysis, master,
                                      FactsProfile(work_permit="EU citizen"), "en")
    assert len(doc.items) >= 2
    assert all(i.origin == "generated" for i in doc.items)
    assert all(i.question and i.answer for i in doc.items)
    # Deterministic: same input, same output.
    doc2 = await provider.write_answers("We need python and docker.", analysis, master,
                                       FactsProfile(work_permit="EU citizen"), "en")
    assert doc.model_dump() == doc2.model_dump()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_answers_ai.py -v`
Expected: FAIL with `AttributeError: 'FakeProvider' object has no attribute 'write_answers'`

- [ ] **Step 3: Extend the protocol**

In `backend/app/ai/base.py`, extend the import to include `AnswersDoc` and `FactsProfile`, then add to `AIProvider` after `outreach`:

```python
    async def write_answers(
        self, jd: str, analysis: JobAnalysis, master: CVData, facts: FactsProfile, language: str
    ) -> AnswersDoc: ...
```

- [ ] **Step 4: Prompt builder**

In `backend/app/ai/prompts.py`, add (match the file's existing style of plain functions returning strings; place near the outreach prompt):

```python
def answers_prompt(jd: str, master_text: str, facts_text: str, language: str) -> str:
    lang_names = {"en": "English", "fr": "French", "de": "German"}
    return f"""You prepare a candidate for the screening questions of ONE job posting.
Write in {lang_names.get(language, "English")}.

Derive 3 to 6 questions a recruiter for THIS posting would realistically ask
(experience depth, specific tools, motivation for this company, availability
specifics beyond the standard facts) and answer them AS the candidate.

HARD RULES:
- Ground every answer ONLY in the CV and the stated facts below. If the
  information is not there, the answer must say the candidate will confirm,
  never an invented specific (no invented years, employers, certificates,
  salaries, or dates).
- Skip questions already covered by the standard facts (work permit, notice
  period, salary, mobility, languages, driving licence, start date).
- 2-4 sentences per answer, first person, concrete, no filler.

JOB POSTING:
{jd}

CANDIDATE CV:
{master_text}

CANDIDATE FACTS:
{facts_text}
"""
```

- [ ] **Step 5: Gemini implementation**

In `backend/app/ai/gemini.py`, extend the schemas import with `AnswersDoc, FactsProfile` and add the method to `GeminiProvider` (same shape as its sibling methods — it calls `self._generate` with a schema):

```python
    async def write_answers(self, jd, analysis, master, facts, language) -> AnswersDoc:
        facts_text = "\n".join(
            f"{k}: {v}" for k, v in facts.model_dump().items() if v
        ) or "(none provided)"
        doc: AnswersDoc = await self._generate(
            prompts.answers_prompt(jd, master.plain_text(), facts_text, language),
            schema=AnswersDoc,
        )
        for item in doc.items:
            item.origin = "generated"
        return doc
```

- [ ] **Step 6: Fake implementation**

In `backend/app/ai/fake.py`, mirror the file's existing deterministic style (check how `outreach` is written there and place alongside):

```python
    async def write_answers(self, jd, analysis, master, facts, language) -> AnswersDoc:
        top = [k.term for k in analysis.keywords[:2]] or ["the stack"]
        return AnswersDoc(
            items=[
                AnswerItem(
                    question=f"How much hands-on experience do you have with {top[0]}?",
                    answer=f"I have used {top[0]} in production as part of my recent work. "
                           f"Details are in my CV; I can walk through concrete projects.",
                    origin="generated",
                ),
                AnswerItem(
                    question=f"Why {analysis.company or 'this company'}?",
                    answer="The role matches the work I already do and the stack I enjoy. "
                           "I want to keep building exactly this kind of system.",
                    origin="generated",
                ),
            ]
        )
```

Add `AnswersDoc, AnswerItem, FactsProfile` to `fake.py`'s schema imports.

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_pipeline_answers_ai.py backend/tests/test_prompts.py -v`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/ai/base.py backend/app/ai/prompts.py backend/app/ai/gemini.py backend/app/ai/fake.py backend/tests/test_pipeline_answers_ai.py
git commit -m "feat(pipeline): write_answers across provider, gemini, fake"
```

---

### Task 10: Fourth artifact in the generation pipeline

**Files:**
- Modify: `backend/app/jobs.py:185-271` (`_pipeline`)
- Test: `backend/tests/test_pipeline_fourth_artifact.py`

**Interfaces:**
- Produces: for jobs whose `gen_params` contains a `posting_id`, a fourth `Document(kind="answers", data=AnswersDoc merged with fixed answers, mode="data")` row. Studio-originated jobs (no `posting_id`) are byte-for-byte unaffected.
- Consumes: `provider.write_answers` (Task 9), `fixed_answers` (Task 8), `FactsProfile` from `job.user`'s `facts` column.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_fourth_artifact.py`:

```python
"""Pipeline jobs get an answers document; studio jobs stay 3-doc."""
import asyncio

import pytest
from sqlalchemy import select

from backend.app.db import session_factory
from backend.app.models import Document, Job, User
from backend.app.schemas import FactsProfile
from backend.tests.conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email


async def _register_and_generate(client, extra_gen=None):
    email = unique_email()
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    body = {
        "job_descriptions": [SAMPLE_JD], "cv_text": SAMPLE_CV_TEXT, "language": "en",
        "template": "onyx", "accent": "#0F62FE", "show_photo": False,
    }
    r = await client.post("/api/generate", json=body)
    assert r.status_code == 200, r.text
    return email, r.json()["jobs"][0]


async def _wait_done(job_id, timeout=30):
    for _ in range(timeout * 10):
        async with session_factory()() as db:
            job = await db.get(Job, job_id)
            if job.status in ("completed", "failed"):
                return job.status
        await asyncio.sleep(0.1)
    raise TimeoutError


@pytest.mark.anyio
async def test_studio_job_still_three_documents(client):
    _, job_id = await _register_and_generate(client)
    assert await _wait_done(job_id) == "completed"
    async with session_factory()() as db:
        kinds = {
            d.kind for d in (await db.execute(select(Document).where(Document.job_id == job_id))).scalars()
        }
    assert kinds == {"cv", "letter", "message"}


@pytest.mark.anyio
async def test_pipeline_job_gets_answers_document(client):
    email, job_id = await _register_and_generate(client)
    assert await _wait_done(job_id) == "completed"
    # Simulate a pipeline-originated job: set posting_id in gen_params and user facts,
    # then re-run the pipeline via the retry endpoint (which replays gen_params).
    async with session_factory()() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.facts = FactsProfile(work_permit="EU citizen").model_dump()
        job = await db.get(Job, job_id)
        job.gen_params = {**(job.gen_params or {}), "posting_id": 42}
        await db.commit()
    r = await client.post(f"/api/jobs/{job_id}/retry")
    assert r.status_code == 200
    new_id = r.json()["id"]
    assert await _wait_done(new_id) == "completed"
    async with session_factory()() as db:
        docs = (await db.execute(select(Document).where(Document.job_id == new_id))).scalars().all()
    kinds = {d.kind for d in docs}
    assert kinds == {"cv", "letter", "message", "answers"}
    answers = next(d for d in docs if d.kind == "answers")
    items = answers.data["items"]
    origins = {i["origin"] for i in items}
    assert "facts" in origins and "generated" in origins
    facts_items = [i for i in items if i["origin"] == "facts"]
    assert facts_items[0]["answer"] == "EU citizen"
```

Note: if the retry endpoint copies `gen_params` verbatim into the new job (check `backend/app/routers/generate.py` retry handler), this exercises the real pipeline path. If retry lives in a different router file, adjust the POST path to match the existing route (`grep -rn "retry" backend/app/routers/`); the tests pin behavior, not routing internals.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_fourth_artifact.py -v`
Expected: `test_studio_job_still_three_documents` PASS, `test_pipeline_job_gets_answers_document` FAIL (kinds missing `"answers"`)

- [ ] **Step 3: Implement**

In `backend/app/jobs.py`:

1. `_run_job` and `spawn_job` already thread `gen_params` implicitly via the DB row; `_pipeline` receives the job row. Read the posting flag at the top of `_pipeline` (after `master = CVData.model_validate(master_data)`):

```python
    gen_params = job.gen_params or {}
    is_pipeline_job = gen_params.get("posting_id") is not None
```

2. In the parallel generation block (lines 186-189), add the fourth task conditionally:

```python
    cv_task = provider.tailor_cv(job.job_description, analysis, master, language, rewrite_intensity)
    letter_task = provider.write_letter(job.job_description, analysis, master, language)
    msg_task = provider.outreach(job.job_description, analysis, master, language)
    if is_pipeline_job:
        from .answers import fixed_answers
        from .schemas import FactsProfile

        user = await db.get(User, job.user_id) if job.user_id else None
        facts = FactsProfile.model_validate((user.facts if user else None) or {})
        answers_task = provider.write_answers(job.job_description, analysis, master, facts, language)
        tailored, letter, message, generated_answers = await asyncio.gather(
            cv_task, letter_task, msg_task, answers_task
        )
        all_answers = fixed_answers(facts, language) + list(generated_answers.items)
    else:
        tailored, letter, message = await asyncio.gather(cv_task, letter_task, msg_task)
        all_answers = None
```

Add `User` to the models import at the top of `jobs.py` (`from .models import Document, Job, Photo, User`).

3. After `msg_doc` is built (line 266-270), add:

```python
    docs_to_add = [cv_doc, letter_doc, msg_doc]
    if all_answers is not None:
        docs_to_add.append(
            Document(
                id=uuid.uuid4().hex, job_id=job.id, user_id=job.user_id, kind="answers",
                title=title, template_id=template, settings=doc_settings,
                data={"items": [a.model_dump() for a in all_answers]}, mode="data",
            )
        )
    db.add_all(docs_to_add)
```

(replacing the existing `db.add_all([cv_doc, letter_doc, msg_doc])`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_pipeline_fourth_artifact.py -v`
Expected: 2 PASS

Full gate: `python -m pytest backend/tests -q`
Expected: all pass (the studio path is untouched; if `test_api.py` document-count assertions exist, they still see 3 docs)

- [ ] **Step 5: Commit**

```bash
git add backend/app/jobs.py backend/tests/test_pipeline_fourth_artifact.py
git commit -m "feat(pipeline): answers document for pipeline-originated jobs"
```

---

### Task 11: Email composer with injection guard and .eml fallback

**Files:**
- Create: `backend/app/mailer.py`
- Modify: `backend/app/config.py` (add `send_cap_daily: int = 15`, `eml_out_dir: str = ""` under the pipeline block)
- Test: `backend/tests/test_pipeline_mailer.py`

**Interfaces:**
- Produces: `build_application_email(sender: str, to: str, subject: str, body: str, attachments: list[tuple[str, bytes]]) -> email.message.EmailMessage` (raises `ValueError` on CR/LF in `sender`/`to`/`subject`); `write_eml(msg, directory: str | Path) -> Path`; `class EmlSender` with `async send(msg) -> str` (returns file path); `Sender` Protocol with `async send(msg) -> str`.
- Consumes: stdlib `email.message`, `email.policy`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_mailer.py`:

```python
"""MIME correctness, header-injection rejection, .eml fallback."""
from pathlib import Path

import pytest

from backend.app.mailer import EmlSender, build_application_email, write_eml

PDF = b"%PDF-1.4 fake"


def _msg():
    return build_application_email(
        sender="alex@example.com",
        to="recrutement@lumina.example",
        subject="Candidature — Ingénieur ML (185XKPT)",
        body="Bonjour,\n\nVeuillez trouver ma candidature ci-jointe.\n\nAlex",
        attachments=[("CV_Alex_Martin.pdf", PDF), ("Lettre_Alex_Martin.pdf", PDF)],
    )


def test_mime_structure():
    msg = _msg()
    assert msg["To"] == "recrutement@lumina.example"
    assert "Candidature" in msg["Subject"]
    parts = list(msg.iter_attachments())
    assert [p.get_filename() for p in parts] == ["CV_Alex_Martin.pdf", "Lettre_Alex_Martin.pdf"]
    assert all(p.get_content_type() == "application/pdf" for p in parts)
    assert "Veuillez trouver" in msg.get_body(("plain",)).get_content()


@pytest.mark.parametrize("field", ["to", "subject", "sender"])
def test_header_injection_rejected(field):
    kwargs = dict(sender="a@b.c", to="x@y.z", subject="Hi", body="B", attachments=[])
    kwargs[field] = "evil\r\nBcc: spam@spam.spam"
    with pytest.raises(ValueError):
        build_application_email(**kwargs)


@pytest.mark.anyio
async def test_eml_sender_writes_file(tmp_path: Path):
    path_str = await EmlSender(tmp_path).send(_msg())
    p = Path(path_str)
    assert p.exists() and p.suffix == ".eml"
    content = p.read_bytes()
    assert b"recrutement@lumina.example" in content and b"application/pdf" in content


def test_write_eml_unique_names(tmp_path: Path):
    a = write_eml(_msg(), tmp_path)
    b = write_eml(_msg(), tmp_path)
    assert a != b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_mailer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.mailer'`

- [ ] **Step 3: Implement**

Create `backend/app/mailer.py`:

```python
"""Application email assembly and sending.

The body is the outreach message; the CV and letter PDFs ride as
attachments. Sends go out as the USER (their Gmail, Task 12) or to a
local .eml file in dev — never from a cvglowup.com address."""
import uuid
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from typing import Protocol

_FORBIDDEN = ("\r", "\n")


def _clean_header(value: str, name: str) -> str:
    if any(ch in value for ch in _FORBIDDEN):
        raise ValueError(f"Illegal newline in {name} header.")
    return value.strip()


def build_application_email(
    sender: str,
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]],
) -> EmailMessage:
    msg = EmailMessage(policy=SMTP)
    msg["From"] = _clean_header(sender, "From")
    msg["To"] = _clean_header(to, "To")
    msg["Subject"] = _clean_header(subject, "Subject")
    msg.set_content(body)
    for filename, blob in attachments:
        msg.add_attachment(
            blob, maintype="application", subtype="pdf", filename=filename
        )
    return msg


def write_eml(msg: EmailMessage, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"application_{uuid.uuid4().hex[:12]}.eml"
    path.write_bytes(bytes(msg))
    return path


class Sender(Protocol):
    async def send(self, msg: EmailMessage) -> str: ...


class EmlSender:
    """Dev fallback: 'sending' writes an .eml the user can open and send."""

    def __init__(self, directory: str | Path):
        self._dir = directory

    async def send(self, msg: EmailMessage) -> str:
        return str(write_eml(msg, self._dir))
```

Add to `backend/app/config.py` under the pipeline block:

```python
    send_cap_daily: int = 15
    eml_out_dir: str = ""  # dev fallback output; empty -> <repo>/eml_out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_pipeline_mailer.py -v`
Expected: 6 PASS (4 tests, one parametrized x3)

- [ ] **Step 5: Commit**

```bash
git add backend/app/mailer.py backend/app/config.py backend/tests/test_pipeline_mailer.py
git commit -m "feat(pipeline): MIME composer, injection guard, .eml sender"
```

---

### Task 12: Gmail OAuth connect and GmailSender

**Files:**
- Modify: `backend/app/mailer.py` (add `GmailSender`)
- Modify: `backend/app/routers/account.py` (add `POST /api/account/gmail/connect`, `DELETE /api/account/gmail`)
- Modify: `backend/app/config.py` (add `google_client_secret: str = ""` under the pipeline block — the OAuth code exchange needs it; `google_client_id` already exists)
- Test: `backend/tests/test_pipeline_gmail.py`

**Interfaces:**
- Produces: `class GmailSender(user_refresh_token: str, client_id: str, client_secret: str, http: httpx.AsyncClient | None = None)` with `async send(msg) -> str` (returns Gmail message id); `TOKEN_URL`, `SEND_URL` constants; REST: `POST /api/account/gmail/connect {code: str, redirect_uri: str}` exchanges an auth code (scope `gmail.send`) and stores `user.gmail_refresh_token`; `DELETE /api/account/gmail` clears it. Frontend obtains the code via Google's standard OAuth popup with the existing `google_client_id`.
- Consumes: `users.gmail_refresh_token` column (Task 1), `build_application_email` (Task 11).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_gmail.py`:

```python
"""GmailSender: refresh-token -> access-token -> raw send. All HTTP mocked."""
import base64

import httpx
import pytest

from backend.app.mailer import SEND_URL, TOKEN_URL, GmailSender, build_application_email


@pytest.mark.anyio
async def test_send_exchanges_token_and_posts_raw():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(TOKEN_URL):
            body = request.content.decode()
            assert "refresh_token=rt-1" in body and "grant_type=refresh_token" in body
            return httpx.Response(200, json={"access_token": "at-9", "expires_in": 3599})
        assert url.startswith(SEND_URL)
        assert request.headers["Authorization"] == "Bearer at-9"
        seen["raw"] = request.content
        return httpx.Response(200, json={"id": "msg-42"})

    msg = build_application_email("a@b.c", "hr@co.fr", "Candidature", "Bonjour", [])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        sender = GmailSender("rt-1", "cid", "csec", http=http)
        message_id = await sender.send(msg)
    assert message_id == "msg-42"
    # The payload is the RFC822 message, base64url-encoded in JSON {"raw": ...}
    import json
    raw = json.loads(seen["raw"])["raw"]
    decoded = base64.urlsafe_b64decode(raw + "==")
    assert b"To: hr@co.fr" in decoded


@pytest.mark.anyio
async def test_gmail_connect_requires_auth(client):
    r = await client.post("/api/account/gmail/connect", json={"code": "x", "redirect_uri": "http://localhost"})
    assert r.status_code in (401, 403)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_gmail.py -v`
Expected: FAIL with `ImportError: cannot import name 'SEND_URL'`

- [ ] **Step 3: Implement `GmailSender`**

Append to `backend/app/mailer.py`:

```python
import base64
import json

import httpx

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/upload/gmail/v1/users/me/messages/send"


class GmailError(Exception):
    """User-presentable Gmail failure (revoked consent, quota, transport)."""


class GmailSender:
    """Sends as the user via their stored refresh token (scope gmail.send).
    We hold ONLY the refresh token Google issued to our client id — never a
    password. Revoking access in the user's Google account kills it."""

    def __init__(self, refresh_token: str, client_id: str, client_secret: str,
                 http: httpx.AsyncClient | None = None):
        self._rt = refresh_token
        self._cid = client_id
        self._csec = client_secret
        self._http = http

    async def _access_token(self, http: httpx.AsyncClient) -> str:
        resp = await http.post(TOKEN_URL, data={
            "grant_type": "refresh_token", "refresh_token": self._rt,
            "client_id": self._cid, "client_secret": self._csec,
        })
        if resp.status_code != 200:
            raise GmailError("Gmail authorization expired or was revoked. Reconnect Gmail in Settings.")
        return resp.json()["access_token"]

    async def send(self, msg) -> str:
        raw = base64.urlsafe_b64encode(bytes(msg)).decode().rstrip("=")
        own = self._http is None
        http = self._http or httpx.AsyncClient(timeout=30)
        try:
            token = await self._access_token(http)
            resp = await http.post(
                SEND_URL,
                params={"uploadType": "media"},
                content=json.dumps({"raw": raw}),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "message/rfc822"},
            )
            if resp.status_code not in (200, 202):
                raise GmailError(f"Gmail send failed ({resp.status_code}).")
            return resp.json().get("id", "")
        finally:
            if own:
                await http.aclose()
```

Note on `Content-Type`: Gmail's upload endpoint accepts `message/rfc822` with the raw RFC822 bytes OR the JSON `{"raw": ...}` metadata form on the non-upload endpoint. The MockTransport test pins the JSON-raw form; if the live API rejects it during phase-2 verification, switch `content=` to `bytes(msg)` with `Content-Type: message/rfc822` and drop the base64 — the test then pins that instead. One of the two documented forms will hold; the seam is one method.

- [ ] **Step 4: Connect/disconnect endpoints**

In `backend/app/routers/account.py` add (same `require_user` guard as Task 8):

```python
import httpx as _httpx

from ..mailer import TOKEN_URL as _GOOGLE_TOKEN_URL


@router.post("/gmail/connect")
async def gmail_connect(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> dict:
    code, redirect_uri = body.get("code", ""), body.get("redirect_uri", "")
    if not code:
        raise HTTPException(status_code=422, detail="Missing authorization code.")
    settings = get_settings()
    async with _httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(_GOOGLE_TOKEN_URL, data={
            "grant_type": "authorization_code", "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
        })
    if resp.status_code != 200 or "refresh_token" not in resp.json():
        raise HTTPException(status_code=400, detail="Google did not grant offline Gmail access.")
    user.gmail_refresh_token = resp.json()["refresh_token"]
    await db.commit()
    return {"connected": True}


@router.delete("/gmail")
async def gmail_disconnect(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> dict:
    user.gmail_refresh_token = None
    await db.commit()
    return {"connected": False}
```

Add `google_client_secret: str = ""` to `backend/app/config.py` and import `get_settings` in `account.py` if not present.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_pipeline_gmail.py -v`
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/mailer.py backend/app/routers/account.py backend/app/config.py backend/tests/test_pipeline_gmail.py
git commit -m "feat(pipeline): Gmail OAuth connect and sender (user's own mailbox)"
```

---

### Task 13: Applications router — board, generate bridge, approve, send

**Files:**
- Create: `backend/app/routers/applications.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_pipeline_router.py`

**Interfaces:**
- Produces REST under `/api/pipeline` (all require login + `user.pipeline_enabled`):
  - `GET /api/pipeline` → `{applications: [{id, status, posting: {id, title, company, location, source, apply_email, apply_url, posted_at}, job_id, sent_at, audit}]}`
  - `POST /api/pipeline/searches {name, keywords, insee, radius_km, contract_type}` / `GET /api/pipeline/searches` / `DELETE /api/pipeline/searches/{id}`
  - `POST /api/pipeline/generate {application_ids: [int], template, accent, language, rewrite_intensity}` → runs quota check, creates one Job per application with `gen_params.posting_id`, advances each to `generated`, returns `{jobs: [...]}`. Uses the user's default master CV (404 if none).
  - `POST /api/pipeline/{app_id}/approve` → `generated → approved`
  - `POST /api/pipeline/{app_id}/reject {note}` → `rejected`
  - `POST /api/pipeline/{app_id}/send {subject?, body?}` → cap check, `approved → sent`; email route requires `posting.apply_email`; attaches CV + letter PDFs from the linked job's documents; body defaults to the job's outreach message text; uses `GmailSender` when `user.gmail_refresh_token` else `EmlSender(settings.eml_out_dir or REPO_ROOT/"eml_out")`; records `sent_via` (`"gmail"`/`"eml"`) and `sent_at`; 409 if the posting has no email (link route: frontend opens `apply_url`, user marks sent manually via `POST /api/pipeline/{app_id}/mark-sent`).
  - `POST /api/pipeline/{app_id}/mark-sent` → `approved → sent` with `sent_via="manual"`.
- Consumes: everything from Tasks 1, 2, 6, 8, 10, 11, 12; `check_quota` from `backend/app/quota.py`; `spawn_job`/`Job` creation pattern from `backend/app/routers/generate.py:84-118`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_router.py`:

```python
"""End-to-end review queue on the fake AI: ingest -> generate -> approve -> send (.eml)."""
import asyncio

import pytest
from sqlalchemy import select

from backend.app.db import session_factory
from backend.app.models import Application, JobPosting, User
from backend.app.pipeline_ingest import ingest
from backend.app.schemas import JobPostingIn
from backend.tests.conftest import SAMPLE_CV_TEXT, SAMPLE_JD, unique_email


async def _setup_user(client, pipeline=True):
    email = unique_email()
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    await client.post("/api/cvs", json={"name": "Master", "raw_text": SAMPLE_CV_TEXT})
    async with session_factory()() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.pipeline_enabled = 1 if pipeline else 0
        await ingest(db, user.id, [
            JobPostingIn(source="ft", external_id="R1", title="ML Engineer", company="Lumina",
                         description=SAMPLE_JD, apply_email="hr@lumina.example"),
        ])
        await db.commit()
        return email, user.id


async def _wait_jobs(client, job_ids, timeout=30):
    for _ in range(timeout * 10):
        snaps = [await client.get(f"/api/jobs/{j}") for j in job_ids]
        if all(s.json()["status"] in ("completed", "failed") for s in snaps):
            return [s.json()["status"] for s in snaps]
        await asyncio.sleep(0.1)
    raise TimeoutError


@pytest.mark.anyio
async def test_full_queue_flow_with_eml(client, tmp_path, monkeypatch):
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "eml_out_dir", str(tmp_path), raising=False)

    email, uid = await _setup_user(client)
    board = (await client.get("/api/pipeline")).json()["applications"]
    assert len(board) == 1 and board[0]["status"] == "inbox"
    app_id = board[0]["id"]
    assert board[0]["posting"]["apply_email"] == "hr@lumina.example"

    r = await client.post("/api/pipeline/generate", json={
        "application_ids": [app_id], "template": "onyx", "accent": "#0F62FE",
        "language": "fr", "rewrite_intensity": "major",
    })
    assert r.status_code == 200, r.text
    assert await _wait_jobs(client, r.json()["jobs"]) == ["completed"]

    board = (await client.get("/api/pipeline")).json()["applications"]
    assert board[0]["status"] == "generated" and board[0]["job_id"]

    assert (await client.post(f"/api/pipeline/{app_id}/approve")).status_code == 200
    r = await client.post(f"/api/pipeline/{app_id}/send", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sent_via"] == "eml" and body["status"] == "sent"
    assert list(tmp_path.glob("*.eml")), "eml file written"


@pytest.mark.anyio
async def test_send_requires_approved_state(client, tmp_path, monkeypatch):
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "eml_out_dir", str(tmp_path), raising=False)
    _, uid = await _setup_user(client)
    app_id = (await client.get("/api/pipeline")).json()["applications"][0]["id"]
    r = await client.post(f"/api/pipeline/{app_id}/send", json={})
    assert r.status_code == 409


@pytest.mark.anyio
async def test_pipeline_flag_gates_access(client):
    await _setup_user(client, pipeline=False)
    assert (await client.get("/api/pipeline")).status_code == 403


@pytest.mark.anyio
async def test_send_cap_enforced(client, tmp_path, monkeypatch):
    from backend.app.config import get_settings
    monkeypatch.setattr(get_settings(), "eml_out_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(get_settings(), "send_cap_daily", 0, raising=False)
    _, uid = await _setup_user(client)
    app_id = (await client.get("/api/pipeline")).json()["applications"][0]["id"]
    r = await client.post("/api/pipeline/generate", json={
        "application_ids": [app_id], "template": "onyx", "accent": "#0F62FE",
        "language": "fr", "rewrite_intensity": "major",
    })
    await _wait_jobs(client, r.json()["jobs"])
    await client.post(f"/api/pipeline/{app_id}/approve")
    r = await client.post(f"/api/pipeline/{app_id}/send", json={})
    assert r.status_code == 429
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_pipeline_router.py -v`
Expected: FAIL with 404s (`/api/pipeline` not mounted)

- [ ] **Step 3: Implement the router**

Create `backend/app/routers/applications.py`:

```python
"""Review-queue API. The queue is the product: nothing sends without an
explicit approve, and nothing sends past the daily cap."""
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import REPO_ROOT, get_settings
from ..db import get_db
from ..mailer import EmlSender, GmailSender, build_application_email
from ..models import Application, Document, Job, JobPosting, MasterCV, SavedSearch, User
from ..pipeline_states import advance
from ..quota import check_quota
from ..jobs import spawn_job
from ..security import get_byok_key, get_current_user

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


async def require_pipeline_user(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Log in first.")
    if not user.pipeline_enabled:
        raise HTTPException(status_code=403, detail="The pipeline is not enabled for this account.")
    return user


class SearchIn(BaseModel):
    name: str = "Search"
    keywords: str = ""
    insee: str = ""
    radius_km: int = 20
    contract_type: str = ""


class PipelineGenerateIn(BaseModel):
    """Local model — deliberately NOT schemas.GenerateIn (different contract)."""

    application_ids: list[int] = Field(min_length=1)
    template: str = "onyx"
    accent: str = "#0F62FE"
    language: str = "fr"
    rewrite_intensity: str = "major"


class SendIn(BaseModel):
    subject: str | None = None
    body: str | None = None


def _app_payload(a: Application, p: JobPosting) -> dict:
    return {
        "id": a.id, "status": a.status, "job_id": a.job_id,
        "sent_via": a.sent_via, "sent_at": a.sent_at.isoformat() if a.sent_at else None,
        "audit": a.audit or [],
        "posting": {
            "id": p.id, "title": p.title, "company": p.company, "location": p.location,
            "source": p.source, "apply_email": p.apply_email, "apply_url": p.apply_url,
            "posted_at": p.posted_at, "contract_type": p.contract_type,
        },
    }


async def _get_app(db: AsyncSession, app_id: int, user: User) -> tuple[Application, JobPosting]:
    row = (
        await db.execute(
            select(Application, JobPosting)
            .join(JobPosting, Application.posting_id == JobPosting.id)
            .where(Application.id == app_id, Application.user_id == user.id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return row


@router.get("")
async def board(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    rows = (
        await db.execute(
            select(Application, JobPosting)
            .join(JobPosting, Application.posting_id == JobPosting.id)
            .where(Application.user_id == user.id)
            .order_by(Application.created_at.desc())
        )
    ).all()
    return {"applications": [_app_payload(a, p) for a, p in rows]}


@router.get("/searches")
async def list_searches(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> list[dict]:
    rows = (await db.execute(select(SavedSearch).where(SavedSearch.user_id == user.id))).scalars()
    return [
        {"id": s.id, "name": s.name, "keywords": s.keywords, "insee": s.insee,
         "radius_km": s.radius_km, "contract_type": s.contract_type, "enabled": s.enabled}
        for s in rows
    ]


@router.post("/searches")
async def create_search(
    body: SearchIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    s = SavedSearch(user_id=user.id, **body.model_dump())
    db.add(s)
    await db.commit()
    return {"id": s.id}


@router.delete("/searches/{search_id}")
async def delete_search(
    search_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    s = await db.get(SavedSearch, search_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(status_code=404, detail="Search not found.")
    await db.delete(s)
    await db.commit()
    return {"ok": True}


@router.post("/generate")
async def generate_for_applications(
    body: PipelineGenerateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
    byok: Annotated[str | None, Depends(get_byok_key)],
) -> dict:
    cv = (
        await db.execute(
            select(MasterCV).where(MasterCV.user_id == user.id)
            .order_by(MasterCV.is_default.desc(), MasterCV.updated_at.desc())
        )
    ).scalars().first()
    if cv is None or cv.data is None:
        raise HTTPException(status_code=404, detail="Save a master CV first.")

    apps: list[tuple[Application, JobPosting]] = []
    for app_id in body.application_ids:
        a, p = await _get_app(db, app_id, user)
        if a.status != "inbox":
            raise HTTPException(status_code=409, detail=f"Application {app_id} is not in the inbox.")
        apps.append((a, p))

    await check_quota(db, user, None, len(apps), byok is not None, body.template)

    language = body.language if body.language in ("en", "fr", "de") else "fr"
    intensity = body.rewrite_intensity if body.rewrite_intensity in ("reshape", "minor", "major", "max_ats") else "major"
    job_ids: list[str] = []
    for a, p in apps:
        gen_params = {
            "master_data": cv.data, "photo_id": None, "template": body.template,
            "accent": body.accent, "show_photo": False, "intensity": intensity,
            "posting_id": p.id,
        }
        job = Job(
            id=uuid.uuid4().hex, user_id=user.id, language=language,
            job_description=p.description, byok=byok is not None, events=[],
            gen_params=gen_params,
        )
        db.add(job)
        a.job_id = job.id
        advance(a, "generated", note=f"job {job.id}")
        job_ids.append(job.id)
    await db.commit()

    for jid in job_ids:
        spawn_job(jid, cv.data, None, body.template, body.accent, False, byok, intensity)
    return {"jobs": job_ids}


@router.post("/{app_id}/approve")
async def approve(
    app_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    a, p = await _get_app(db, app_id, user)
    try:
        advance(a, "approved")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    return _app_payload(a, p)


class RejectIn(BaseModel):
    note: str = ""


@router.post("/{app_id}/reject")
async def reject(
    app_id: int,
    body: RejectIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    a, p = await _get_app(db, app_id, user)
    try:
        advance(a, "rejected", note=body.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    return _app_payload(a, p)


@router.post("/{app_id}/mark-sent")
async def mark_sent(
    app_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    a, p = await _get_app(db, app_id, user)
    try:
        advance(a, "sent", note="applied manually via link")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    a.sent_via = "manual"
    a.sent_at = datetime.now(UTC)
    await db.commit()
    return _app_payload(a, p)


async def _sent_today(db: AsyncSession, user_id: int) -> int:
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        await db.execute(
            select(func.count(Application.id)).where(
                Application.user_id == user_id,
                Application.sent_at >= day_start,
                Application.sent_via.in_(("gmail", "eml")),
            )
        )
    ).scalar_one()


@router.post("/{app_id}/send")
async def send(
    app_id: int,
    body: SendIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_pipeline_user)],
) -> dict:
    a, p = await _get_app(db, app_id, user)
    if a.status != "approved":
        raise HTTPException(status_code=409, detail="Approve the application first.")
    if not p.apply_email:
        raise HTTPException(
            status_code=409,
            detail="This posting has no application email. Open the posting link and use mark-sent.",
        )
    settings = get_settings()
    if await _sent_today(db, user.id) >= settings.send_cap_daily:
        raise HTTPException(status_code=429, detail=f"Daily send cap reached ({settings.send_cap_daily}).")

    docs = (
        await db.execute(select(Document).where(Document.job_id == a.job_id))
    ).scalars().all()
    cv_doc = next((d for d in docs if d.kind == "cv"), None)
    letter_doc = next((d for d in docs if d.kind == "letter"), None)
    msg_doc = next((d for d in docs if d.kind == "message"), None)
    if cv_doc is None or cv_doc.pdf is None or letter_doc is None or letter_doc.pdf is None:
        raise HTTPException(status_code=409, detail="Documents are not ready for this application.")

    full_name = (cv_doc.data or {}).get("full_name", "") or user.email
    safe_name = full_name.replace(" ", "_") or "Candidate"
    subject = body.subject or f"Candidature - {p.title}" + (f" - {full_name}" if full_name else "")
    email_body = body.body or (msg_doc.text_content if msg_doc else "") or "Veuillez trouver ma candidature ci-jointe."
    msg = build_application_email(
        sender=user.email, to=p.apply_email, subject=subject, body=email_body,
        attachments=[(f"CV_{safe_name}.pdf", cv_doc.pdf), (f"Lettre_{safe_name}.pdf", letter_doc.pdf)],
    )
    if user.gmail_refresh_token:
        sender = GmailSender(user.gmail_refresh_token, settings.google_client_id, settings.google_client_secret)
        via = "gmail"
    else:
        sender = EmlSender(settings.eml_out_dir or str(REPO_ROOT / "eml_out"))
        via = "eml"
    try:
        await sender.send(msg)
    except Exception as exc:  # GmailError or IO — the row stays approved for an explicit retry
        raise HTTPException(status_code=502, detail=f"Send failed: {exc}") from exc
    advance(a, "sent", note=f"via {via} to {p.apply_email}")
    a.sent_via = via
    a.sent_at = datetime.now(UTC)
    await db.commit()
    return _app_payload(a, p)
```

In `backend/app/main.py` line 17 add `applications` to the routers import, and include it next to the others: `app.include_router(applications.router)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_pipeline_router.py -v`
Expected: 5 PASS

Full gate: `python -m pytest backend/tests -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/applications.py backend/app/main.py backend/tests/test_pipeline_router.py
git commit -m "feat(pipeline): review-queue API — board, generate, approve, send with cap"
```

---

### Task 14: Frontend — API client and Pipeline board

**Files:**
- Modify: `frontend/src/api.ts` (types + methods)
- Create: `frontend/src/pages/Pipeline.tsx`
- Modify: `frontend/src/App.tsx` (route)
- Modify: `frontend/src/components/Nav.tsx` (nav link, only when `me.pipeline_enabled`)
- Modify: `frontend/src/i18n.tsx` (keys in en, fr, de)

**Interfaces:**
- Consumes: `/api/pipeline*` REST from Task 13; existing `request<T>` helper and `api` object pattern (`frontend/src/api.ts:123-199`); `useI18n` hook; react-router `Route` pattern (`frontend/src/App.tsx:26-33`).
- Produces: `api.pipeline()`, `api.pipelineGenerate(ids, opts)`, `api.pipelineApprove(id)`, `api.pipelineReject(id, note)`, `api.pipelineSend(id, body)`, `api.pipelineMarkSent(id)`, `api.pipelineSearches()`, `api.createPipelineSearch(body)`, `api.deletePipelineSearch(id)`; `PipelineApp` TS type; `/pipeline` route. The `Me` type gains `pipeline_enabled: boolean` (backend: confirm `/api/auth/me` payload includes it — if not, add the field to the me-serializer in `backend/app/routers/auth.py` in this task and assert it in `backend/tests/test_api.py`'s me-test).

- [ ] **Step 1: Extend `api.ts`**

Add types near the other interfaces in `frontend/src/api.ts`:

```typescript
export interface PipelinePosting {
  id: number; title: string; company: string; location: string; source: string;
  apply_email: string | null; apply_url: string | null; posted_at: string; contract_type: string;
}
export interface PipelineApp {
  id: number; status: "inbox" | "generated" | "approved" | "sent" | "replied" | "rejected";
  job_id: string | null; sent_via: string | null; sent_at: string | null;
  audit: { ts: string; from: string; to: string; note: string }[];
  posting: PipelinePosting;
}
export interface PipelineSearch {
  id: number; name: string; keywords: string; insee: string; radius_km: number;
  contract_type: string; enabled: boolean;
}
```

Add methods inside the `api` object (after the `generate` entry):

```typescript
  pipeline: () => request<{ applications: PipelineApp[] }>("/api/pipeline"),
  pipelineGenerate: (application_ids: number[], opts: {
    template: string; accent: string; language: string; rewrite_intensity: string;
  }) => request<{ jobs: string[] }>("/api/pipeline/generate", {
    method: "POST", body: JSON.stringify({ application_ids, ...opts }),
  }),
  pipelineApprove: (id: number) =>
    request<PipelineApp>(`/api/pipeline/${id}/approve`, { method: "POST" }),
  pipelineReject: (id: number, note: string) =>
    request<PipelineApp>(`/api/pipeline/${id}/reject`, { method: "POST", body: JSON.stringify({ note }) }),
  pipelineSend: (id: number, body: { subject?: string; body?: string }) =>
    request<PipelineApp>(`/api/pipeline/${id}/send`, { method: "POST", body: JSON.stringify(body) }),
  pipelineMarkSent: (id: number) =>
    request<PipelineApp>(`/api/pipeline/${id}/mark-sent`, { method: "POST" }),
  pipelineSearches: () => request<PipelineSearch[]>("/api/pipeline/searches"),
  createPipelineSearch: (body: { name: string; keywords: string; insee: string; radius_km: number; contract_type: string }) =>
    request<{ id: number }>("/api/pipeline/searches", { method: "POST", body: JSON.stringify(body) }),
  deletePipelineSearch: (id: number) =>
    request<{ ok: true }>(`/api/pipeline/searches/${id}`, { method: "DELETE" }),
```

- [ ] **Step 2: Build the board page**

Create `frontend/src/pages/Pipeline.tsx`. Follow the app's visual language (light app pages, Tailwind utility classes as used in `Dashboard.tsx` — read it first and reuse its container/header classes). Functional requirements:

```tsx
/* Review queue: columns per status, cards per application. */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type PipelineApp } from "../api";
import { useI18n } from "../i18n";

const COLUMNS: PipelineApp["status"][] = ["inbox", "generated", "approved", "sent"];

export default function Pipeline() {
  const { t } = useI18n();
  const [apps, setApps] = useState<PipelineApp[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");

  const reload = useCallback(() => {
    api.pipeline().then((r) => setApps(r.applications)).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { reload(); const t = setInterval(reload, 15000); return () => clearInterval(t); }, [reload]);

  const act = async (id: number, fn: () => Promise<unknown>) => {
    setBusy(id); setError("");
    try { await fn(); } catch (e) { setError((e as Error).message); }
    setBusy(null); reload();
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("pipeline.title")}</h1>
        <Link to="/settings" className="text-sm underline">{t("pipeline.settingsLink")}</Link>
      </div>
      {error && <div className="mb-4 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {COLUMNS.map((col) => (
          <section key={col}>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide opacity-60">
              {t(`pipeline.col.${col}`)} ({apps.filter((a) => a.status === col).length})
            </h2>
            <div className="space-y-3">
              {apps.filter((a) => a.status === col).map((a) => (
                <article key={a.id} className="rounded-lg border bg-white p-3 shadow-sm">
                  <div className="text-sm font-semibold">{a.posting.title}</div>
                  <div className="text-xs opacity-70">{a.posting.company} · {a.posting.location}</div>
                  <div className="mt-1 text-[11px] uppercase opacity-50">{a.posting.source}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {a.status === "inbox" && (
                      <button disabled={busy === a.id}
                        onClick={() => act(a.id, () => api.pipelineGenerate([a.id], {
                          template: "onyx", accent: "#C2551B", language: "fr", rewrite_intensity: "major",
                        }))}
                        className="rounded bg-black px-2 py-1 text-xs text-white">
                        {t("pipeline.generate")}
                      </button>
                    )}
                    {a.status === "generated" && (
                      <>
                        {a.job_id && (
                          <Link className="rounded border px-2 py-1 text-xs" to={`/studio?job=${a.job_id}`}>
                            {t("pipeline.viewDocs")}
                          </Link>
                        )}
                        <button disabled={busy === a.id}
                          onClick={() => act(a.id, () => api.pipelineApprove(a.id))}
                          className="rounded bg-black px-2 py-1 text-xs text-white">
                          {t("pipeline.approve")}
                        </button>
                      </>
                    )}
                    {a.status === "approved" && (a.posting.apply_email ? (
                      <button disabled={busy === a.id}
                        onClick={() => act(a.id, () => api.pipelineSend(a.id, {}))}
                        className="rounded bg-black px-2 py-1 text-xs text-white">
                        {t("pipeline.send")}
                      </button>
                    ) : (
                      <>
                        {a.posting.apply_url && (
                          <a className="rounded border px-2 py-1 text-xs" href={a.posting.apply_url}
                             target="_blank" rel="noreferrer">
                            {t("pipeline.openPosting")}
                          </a>
                        )}
                        <button disabled={busy === a.id}
                          onClick={() => act(a.id, () => api.pipelineMarkSent(a.id))}
                          className="rounded border px-2 py-1 text-xs">
                          {t("pipeline.markSent")}
                        </button>
                      </>
                    ))}
                    {a.status !== "sent" && (
                      <button disabled={busy === a.id}
                        onClick={() => act(a.id, () => api.pipelineReject(a.id, ""))}
                        className="rounded border px-2 py-1 text-xs opacity-60">
                        {t("pipeline.reject")}
                      </button>
                    )}
                    {a.status === "sent" && (
                      <span className="text-xs opacity-60">{a.sent_via} · {a.sent_at?.slice(0, 10)}</span>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
```

Adjust the container/card classes to match `Dashboard.tsx`'s actual classes after reading it — the structure above is the contract, the exact class strings follow the existing page.

- [ ] **Step 3: Route and nav**

In `frontend/src/App.tsx` add `import Pipeline from "./pages/Pipeline";` and a route `<Route path="/pipeline" element={<Pipeline />} />` next to the others. In `frontend/src/components/Nav.tsx`, add a link to `/pipeline` labeled `t("nav.pipeline")`, rendered only when the session user has `pipeline_enabled` (follow how Nav reads the session store for auth-only links).

- [ ] **Step 4: i18n keys**

In `frontend/src/i18n.tsx` add to each language dict:

en: `"nav.pipeline": "Pipeline"`, `"pipeline.title": "Application pipeline"`, `"pipeline.settingsLink": "Searches & facts"`, `"pipeline.col.inbox": "Inbox"`, `"pipeline.col.generated": "Generated"`, `"pipeline.col.approved": "Approved"`, `"pipeline.col.sent": "Sent"`, `"pipeline.generate": "Generate documents"`, `"pipeline.viewDocs": "View documents"`, `"pipeline.approve": "Approve"`, `"pipeline.send": "Send application"`, `"pipeline.openPosting": "Open posting"`, `"pipeline.markSent": "Mark as sent"`, `"pipeline.reject": "Reject"`

fr: `"nav.pipeline": "Pipeline"`, `"pipeline.title": "Suivi des candidatures"`, `"pipeline.settingsLink": "Recherches et infos"`, `"pipeline.col.inbox": "Boîte de réception"`, `"pipeline.col.generated": "Générées"`, `"pipeline.col.approved": "Approuvées"`, `"pipeline.col.sent": "Envoyées"`, `"pipeline.generate": "Générer les documents"`, `"pipeline.viewDocs": "Voir les documents"`, `"pipeline.approve": "Approuver"`, `"pipeline.send": "Envoyer la candidature"`, `"pipeline.openPosting": "Ouvrir l'offre"`, `"pipeline.markSent": "Marquer envoyée"`, `"pipeline.reject": "Écarter"`

de: `"nav.pipeline": "Pipeline"`, `"pipeline.title": "Bewerbungs-Pipeline"`, `"pipeline.settingsLink": "Suchen & Fakten"`, `"pipeline.col.inbox": "Eingang"`, `"pipeline.col.generated": "Generiert"`, `"pipeline.col.approved": "Freigegeben"`, `"pipeline.col.sent": "Gesendet"`, `"pipeline.generate": "Dokumente generieren"`, `"pipeline.viewDocs": "Dokumente ansehen"`, `"pipeline.approve": "Freigeben"`, `"pipeline.send": "Bewerbung senden"`, `"pipeline.openPosting": "Anzeige öffnen"`, `"pipeline.markSent": "Als gesendet markieren"`, `"pipeline.reject": "Verwerfen"`

If `backend/tests/test_language.py` enforces key parity across languages (it does per its role as the add-a-language checklist), run it and satisfy any structural checks it makes.

- [ ] **Step 5: Build and verify**

Run: `npm run build` in `frontend/`
Expected: build succeeds, no TS errors

Run: `python -m pytest backend/tests/test_language.py -q`
Expected: PASS

Start the dev server (`.claude/launch.json` config) and verify in the browser: log in with a `pipeline_enabled` account (flip the flag in SQLite: `UPDATE users SET pipeline_enabled=1 WHERE email='...'`), seed one posting via `python -c` calling `ingest` or re-use the poller with configured keys, then walk inbox → generate → approve → send (.eml lands in `eml_out/`). Screenshot the board.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.ts frontend/src/pages/Pipeline.tsx frontend/src/App.tsx frontend/src/components/Nav.tsx frontend/src/i18n.tsx
git commit -m "feat(pipeline): review-queue board UI with i18n (en/fr/de)"
```

---

### Task 15: Frontend — facts profile and saved searches in Settings

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`
- Modify: `frontend/src/api.ts` (facts methods)
- Modify: `frontend/src/i18n.tsx` (keys)

**Interfaces:**
- Consumes: `GET/PUT /api/account/facts` (Task 8), searches CRUD (Task 13/14), Gmail connect endpoints (Task 12).
- Produces: `api.facts()`, `api.updateFacts(body)` methods; a "Job pipeline" section in Settings visible only when `pipeline_enabled`: facts form (7 fields), saved-search list with add/delete, Gmail connect/disconnect button (Google OAuth code flow popup using the existing Google client id; on success POST the code to `/api/account/gmail/connect` with the popup redirect URI).

- [ ] **Step 1: api.ts additions**

```typescript
  facts: () => request<FactsProfile>("/api/account/facts"),
  updateFacts: (body: FactsProfile) =>
    request<FactsProfile>("/api/account/facts", { method: "PUT", body: JSON.stringify(body) }),
  gmailConnect: (code: string, redirect_uri: string) =>
    request<{ connected: boolean }>("/api/account/gmail/connect", {
      method: "POST", body: JSON.stringify({ code, redirect_uri }),
    }),
  gmailDisconnect: () => request<{ connected: boolean }>("/api/account/gmail", { method: "DELETE" }),
```

with the type:

```typescript
export interface FactsProfile {
  work_permit: string; notice_period: string; salary_range: string; mobility: string;
  languages: string; driving_licence: string; availability: string;
}
```

- [ ] **Step 2: Settings section**

In `frontend/src/pages/Settings.tsx`, add a section following the page's existing card/section markup (read the file first, reuse its patterns — BYOK section is the closest sibling). Contents: facts form, saved-searches list with add/delete, Gmail connect. Render the whole section only when the session user has `pipeline_enabled`. The facts form, concretely (adapt class names to the page's existing inputs):

```tsx
const FACT_FIELDS = [
  "work_permit", "notice_period", "salary_range", "mobility",
  "languages", "driving_licence", "availability",
] as const;

const [facts, setFacts] = useState<FactsProfile | null>(null);
const [savedNote, setSavedNote] = useState(false);
useEffect(() => { api.facts().then(setFacts).catch(() => {}); }, []);

{facts && (
  <div className="grid gap-3 sm:grid-cols-2">
    {FACT_FIELDS.map((f) => (
      <label key={f} className="block text-sm">
        <span className="mb-1 block opacity-70">{t(`settings.facts.${f}`)}</span>
        <input
          className="w-full rounded border px-2 py-1.5"
          value={facts[f]}
          onChange={(e) => setFacts({ ...facts, [f]: e.target.value })}
        />
      </label>
    ))}
    <button
      className="rounded bg-black px-3 py-1.5 text-sm text-white sm:col-span-2 sm:justify-self-start"
      onClick={async () => { await api.updateFacts(facts); setSavedNote(true); setTimeout(() => setSavedNote(false), 2000); }}
    >
      {savedNote ? "✓" : t("settings.facts.save")}
    </button>
  </div>
)}
```

The saved-searches block follows the same list+form shape as the saved-CV manager already in the app (name, keywords, insee, radius_km inputs; `api.createPipelineSearch` on add, `api.deletePipelineSearch` per row). Gmail popup flow:

```typescript
const connectGmail = () => {
  const redirect = `${window.location.origin}/settings`;
  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID, redirect_uri: redirect, response_type: "code",
    scope: "https://www.googleapis.com/auth/gmail.send", access_type: "offline", prompt: "consent",
  });
  window.location.assign(`https://accounts.google.com/o/oauth2/v2/auth?${params}`);
};
// On mount: if the URL has ?code=..., call api.gmailConnect(code, `${window.location.origin}/settings`)
// then strip the query with history.replaceState.
```

`GOOGLE_CLIENT_ID` comes from wherever the login button already reads it (`/api/config` payload — check `AppConfig` in api.ts).

- [ ] **Step 3: i18n keys**

Add in all three languages (same pattern as Task 14): `settings.pipeline.title`, `settings.facts.title`, one label per facts field (`settings.facts.work_permit`, `.notice_period`, `.salary_range`, `.mobility`, `.languages`, `.driving_licence`, `.availability`), `settings.facts.save`, `settings.searches.title`, `settings.searches.add`, `settings.gmail.connect`, `settings.gmail.disconnect`, `settings.gmail.connected`. French and German translations written out, not copied English.

- [ ] **Step 4: Build and verify**

Run: `npm run build` in `frontend/`
Expected: success

Browser: save facts, add a search, reload, both persist. If Google client id is present in dev, walk the Gmail consent once; otherwise verify the button renders and the disconnect path works against a manually set token.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.ts frontend/src/pages/Settings.tsx frontend/src/i18n.tsx
git commit -m "feat(pipeline): settings — facts profile, saved searches, gmail connect"
```

---

### Task 16: Answers faithfulness eval

**Files:**
- Create: `backend/evals/answers_faithfulness.py`
- Test: `backend/tests/test_answers_eval_harness.py`

**Interfaces:**
- Produces: `extract_claims(items: list[dict]) -> list[str]` (regex-pulls years, durations, named employers/certs from answers), `judge_faithful(answer_claims, cv_text, facts_text) -> list[str]` (returns claims NOT grounded in either source — deterministic string containment after normalization, reusing `backend/app/ats.py:normalize`), and a `main()` that runs the live provider over `EVAL_CASES` and fails (exit 1) if any generated answer contains an ungrounded specific. Threshold: zero invented facts.
- Consumes: provider `write_answers` (Task 9), `normalize` from `ats.py`.

- [ ] **Step 1: Write the failing gate test (harness only, fake provider, free)**

Create `backend/tests/test_answers_eval_harness.py`:

```python
"""The eval harness itself is deterministic and gate-tested; the paid run
is `python -m backend.evals.answers_faithfulness` before ship and nightly."""
from backend.evals.answers_faithfulness import extract_claims, judge_faithful

CV = "Alex Martin. ML engineer, 4 years. Built RAG platform on GCP with pytorch."
FACTS = "work_permit: EU citizen"


def test_extract_claims_finds_specifics():
    claims = extract_claims([
        {"question": "q", "answer": "I have 7 years of experience and an AWS certification.", "origin": "generated"},
    ])
    assert any("7 years" in c for c in claims)
    assert any("aws" in c.lower() for c in claims)


def test_judge_flags_invented_and_passes_grounded():
    invented = judge_faithful(["7 years"], CV, FACTS)
    assert invented == ["7 years"]
    grounded = judge_faithful(["4 years", "pytorch"], CV, FACTS)
    assert grounded == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_answers_eval_harness.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.evals.answers_faithfulness'`

- [ ] **Step 3: Implement**

Create `backend/evals/answers_faithfulness.py` (check `backend/evals/` for an existing `__init__.py` and runner conventions from `docgen_compare` and follow them):

```python
"""Periodic eval: generated screening answers must not invent facts.

Gate-tested parts: extract_claims / judge_faithful (deterministic).
Paid part: main() calls the live provider over EVAL_CASES.
Pass threshold: ZERO ungrounded specifics across all cases."""
import asyncio
import re
import sys

from backend.app.ats import normalize

_CLAIM_PATTERNS = [
    re.compile(r"\b\d+\s+(?:years?|ans?|jahren?)\b", re.IGNORECASE),
    re.compile(r"\b(?:certified|certification|certifié|zertifiziert)\s*(?:in|en)?\s*\w+", re.IGNORECASE),
    re.compile(r"\b(?:AWS|GCP|Azure|Kubernetes|PhD|Master|Bachelor)\b[\w\s]{0,20}", re.IGNORECASE),
    re.compile(r"\b\d{4,6}\s*(?:€|EUR|euros?)\b", re.IGNORECASE),
]


def extract_claims(items: list[dict]) -> list[str]:
    claims: list[str] = []
    for item in items:
        if item.get("origin") != "generated":
            continue
        for pattern in _CLAIM_PATTERNS:
            claims.extend(m.group(0).strip() for m in pattern.finditer(item.get("answer", "")))
    return claims


def judge_faithful(claims: list[str], cv_text: str, facts_text: str) -> list[str]:
    haystack = normalize(cv_text + " " + facts_text)
    return [c for c in claims if normalize(c).strip() not in haystack]


EVAL_CASES = [
    {
        "jd": "Lumina AI hires an ML Engineer in Toulouse: python, pytorch, RAG, GCP, docker.",
        "cv": "Alex Martin. ML engineer, 4 years. Built RAG platform on GCP with pytorch and docker.",
        "facts": {"work_permit": "EU citizen", "salary_range": "45-55k EUR"},
        "language": "fr",
    },
    {
        "jd": "Aerotech seeks a Data Engineer: airflow, kubernetes, python, on-site Toulouse.",
        "cv": "Alex Martin. Data/ML engineer, 4 years, airflow and kubernetes daily.",
        "facts": {"notice_period": "1 month"},
        "language": "en",
    },
]


async def _run() -> int:
    from backend.app.ai import get_provider
    from backend.app.schemas import CVData, FactsProfile, JobAnalysis

    provider = get_provider(None)
    failures = 0
    for i, case in enumerate(EVAL_CASES):
        analysis = JobAnalysis(job_title="Role", company="Co")
        master = CVData(full_name="Alex Martin", summary=case["cv"])
        facts = FactsProfile.model_validate(case["facts"])
        doc = await provider.write_answers(case["jd"], analysis, master, facts, case["language"])
        facts_text = " ".join(v for v in case["facts"].values())
        invented = judge_faithful(extract_claims([x.model_dump() for x in doc.items]),
                                  master.plain_text() + " " + case["cv"], facts_text)
        status = "PASS" if not invented else f"FAIL invented={invented}"
        print(f"case {i}: {status}")
        failures += bool(invented)
    print(f"faithfulness: {len(EVAL_CASES) - failures}/{len(EVAL_CASES)} passed (threshold: all)")
    return 1 if failures else 0


def main() -> None:
    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_answers_eval_harness.py -v`
Expected: 2 PASS

Paid run (needs `GEMINI_API_KEY` in `.env`, run once before ship):
`python -m backend.evals.answers_faithfulness`
Expected: `faithfulness: 2/2 passed`

- [ ] **Step 5: Full gate + commit**

Run: `python -m pytest backend/tests -q`
Expected: all pass

```bash
git add backend/evals/answers_faithfulness.py backend/tests/test_answers_eval_harness.py
git commit -m "feat(pipeline): answers faithfulness eval (zero invented facts)"
```

---

## Post-plan checklist (execution session, not tasks)

- Register the France Travail app on francetravail.io, put `FT_CLIENT_ID`/`FT_CLIENT_SECRET` in `.env`, confirm the two endpoint constants, and run one live `poll_once()` for the Toulouse search. Measure the share of postings with `apply_email` (spec open item).
- Adzuna key into `.env` (`ADZUNA_APP_ID`/`ADZUNA_APP_KEY`).
- Google Cloud console: add the `gmail.send` scope to the OAuth consent screen; set `GOOGLE_CLIENT_SECRET` in `.env`.
- Flip `pipeline_enabled=1` for Ayman's account; create the Toulouse saved search; dogfood the full loop.
- Update the cvglowup-runbook skill with: pipeline env vars, the internal poll endpoint + token, the eml_out directory, and the SQLite flag-flip command.
- Extend the language-quality eval harness with pipeline-generated French lettre samples (spec eval item; existing harness, new inputs).
- Wire the outcome metric: a weekly query over `applications` (`sent` per week; avg minutes `created_at → sent_at`) printed by a small script or added to the admin/ops tooling, so the spec's success number is visible without SQL by hand.
- Cloud Scheduler job (prod rollout, gated on Ayman): POST /api/internal/poll hourly with `X-Internal-Token`.
