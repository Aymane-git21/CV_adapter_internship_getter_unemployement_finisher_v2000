# CV Glowup

**Recruiters spend ~7 seconds on a CV. CV Glowup makes them count.**

Paste a job posting (or ten — they run in parallel). CV Glowup rewrites your CV
and cover letter around it, typesets them in **milliseconds** with a Typst
engine, and drops you into an Overleaf-style studio: structured forms on the
left, the recruiter-ready A4 page on the right, re-rendering live as you edit —
through forms, raw Typst source, or a chat assistant. English & French.

## Architecture

```
frontend/  React 18 + TS + Vite + Tailwind v4        backend/  FastAPI (async)
┌─────────────────────────────────────┐              ┌─────────────────────────────────┐
│ Landing · Studio · Dashboard · $$$  │   fetch/SSE  │ google-genai (structured JSON   │
│ Studio: forms | source | chat       │ ───────────► │  out — the LLM never writes     │
│   ⇄ live SVG preview (the paper)    │ ◄─────────── │  markup) → Typst renderer       │
└─────────────────────────────────────┘              │ Jobs/docs in Postgres · quotas  │
                                                     │ Stripe (env-gated) · BYOK       │
templates/typst/  3 CV designs + letter, IBM Plex    └─────────────────────────────────┘
```

Key decisions:

- **Typst replaces LaTeX.** ~0.2 s compiles, one ~30 MB binary instead of
  ~3 GB of texlive. The browser preview is the same engine output (SVG).
- **The LLM emits structured JSON** (`CVData` / `LetterData` schemas enforced
  by `response_schema`); deterministic templates render it. Generation can no
  longer produce documents that fail to compile.
- **Honest ATS scoring.** Keywords are extracted once per job posting; both
  the master and tailored CVs are measured against the same list. The
  before/after delta is computed, never asked of the model.
- **Editable source.** Documents are self-contained `.typ` files with the data
  embedded as a literal — what you see in the source editor is the whole truth.
  Compiles run jailed under `templates/` so user source can't read anything else.
- **State in the database** (SQLite dev / Postgres prod), so any number of
  instances can serve any job's progress. SSE streams updates.
- **Works offline.** Without a Gemini key the backend swaps in a deterministic
  fake provider — the entire product flow (and the test suite) runs keyless.

## Development

```powershell
# backend (Python 3.12) — http://127.0.0.1:8011
py -3.12 -m venv .venv
.venv\Scripts\pip install -r backend/requirements-dev.txt
winget install Typst.Typst
copy .env.example .env          # add GEMINI_API_KEY, or leave empty for offline mode
.venv\Scripts\python -m backend.scripts.serve

# frontend with HMR — http://localhost:5173 (proxies /api to 8011... see vite.config.ts)
cd frontend && npm install && npm run dev

# or serve the built SPA straight from FastAPI:
cd frontend && npm run build
```

### Tests

```powershell
.venv\Scripts\python -m pytest backend/tests -q   # 24 tests: golden compiles, e2e API, quotas
.venv\Scripts\python -m ruff check backend
cd frontend && npm run build                       # typecheck + bundle
```

`backend/scripts/smoke_gemini.py` exercises the real Gemini path end-to-end
(costs a few flash calls).

## Plans & quotas (server-enforced)

| | Guest | Free | Plus | Pro | Your own API key |
|---|---|---|---|---|---|
| Generations/day | 1 | 3 | 30 | fair-use | **unlimited** |
| Parallel postings | 1 | 1 | 3 | 10 | 3 |
| Templates | 1 | 2 | 3 | 3 | 3 |

BYOK: the user's Gemini key lives in their browser only, is sent per-request,
and is never stored or logged server-side.

## Deploying

See [docs/deploy.md](docs/deploy.md) — Cloud Run quickstart, Secret Manager
setup, GitHub Actions CI/CD, domain mapping, and legacy-account migration.

## Repository layout

```
backend/app/        FastAPI app (routers, AI providers, Typst service, quotas)
backend/tests/      pytest suite + fixtures
frontend/src/       React app (pages/Studio is the core)
templates/typst/    document templates + IBM Plex fonts (OFL)
docs/               deployment guide
.github/workflows/  CI + Cloud Run deploy
```

## License

[MIT](LICENSE). IBM Plex fonts under the [OFL](templates/typst/fonts/OFL-LICENSE.txt).
