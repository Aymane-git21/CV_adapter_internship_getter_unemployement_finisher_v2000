---
name: cvglowup-runbook
description: How to run, build, test, and deploy CV Glowup locally (Windows) and on Google Cloud Run. Use when starting dev servers, building the Docker image, deploying, or touching env/config.
---

# CV Glowup Runbook (rehaul v2 — June 2026)

## Stack

- **Backend**: FastAPI (async) in `backend/app/` — routers, google-genai AI providers (+ deterministic offline fake), Typst render service, Postgres/SQLite job state, SSE progress, quotas, Stripe (env-gated). Tests in `backend/tests/` (pytest, 24 tests incl. golden Typst compiles and a full e2e API flow).
- **Frontend**: React 18 + TypeScript + Vite + Tailwind v4 in `frontend/`. Studio = the core (split panes, CodeMirror Typst source, chat editing, SVG live preview).
- **Documents**: Typst templates in `templates/typst/` (onyx/classic/compact + letter), IBM Plex fonts shipped in-repo. The LLM outputs structured JSON; templates render it (see typst-doc-engine skill).

## Run locally (Windows)

```powershell
# backend — http://127.0.0.1:8011 (also serves frontend/dist if built)
.venv\Scripts\python -m backend.scripts.serve

# frontend HMR — http://localhost:5173 (vite proxies /api -> 8011)
cd frontend; npm run dev
```

- `.env` needs `SECRET_KEY` (+ `GEMINI_API_KEY` for real AI; without it, or with `CVG_FAKE_AI=1`, the offline provider runs the whole product deterministically — ideal for UI work and tests).
- Typst CLI: `winget install Typst.Typst` (config auto-discovers the winget path).
- DB: SQLite file `cvglowup.db` at repo root by default; `DATABASE_URL` for Postgres.
- The preview tooling launches via `.claude/launch.json` (port 8011, `backend.scripts.serve`).

## Test / lint

```powershell
.venv\Scripts\python -m pytest backend/tests -q
.venv\Scripts\python -m ruff check backend
cd frontend; npm run build        # tsc + vite
.venv\Scripts\python -m backend.scripts.smoke_gemini   # live Gemini smoke (costs ~5 flash calls)
```

## Deploy

**All deploys go through the zero-downtime protocol**: `python ops/deploy.py deploy` (gate tests -> `--no-traffic` candidate -> smoke on tagged URL -> traffic promote -> prod smoke with auto-rollback). Rollback: `python ops/deploy.py rollback` (traffic shift, seconds, no build). `ops/README.md` documents the protocol; runtime env/secrets/resources are declared at the top of `ops/deploy.py` (manual `gcloud run services update` changes get wiped on next deploy — change the script). Smoke checks use `/api/healthz` (DB ping); plain `/healthz` is intercepted by Google's edge on *.run.app and never reaches the app. GitHub Actions: `ci.yml` on every push, `deploy.yml` on manual dispatch / `v*` tags, `rollback.yml` on dispatch (need `GCP_SA_KEY` secret + `GCP_PROJECT_ID` variable). Docker image = node build stage + python:3.12-slim + typst binary (~250 MB); secrets are `SECRET_KEY`, `GEMINI_API_KEY`, `DATABASE_URL` in Secret Manager.

## Gotchas

- **PowerShell 5.1 mangles UTF-8 when round-tripping file content** (`Get-Content | Set-Content` turned em-dashes into mojibake once). Use the Edit/Write tools on template/source files, never PS string pipelines.
- PS here-strings in commit messages break unpredictably — commit with `git commit -F <file>`.
- Typst SVG output renders text as glyph outlines: don't assert on strings inside SVGs in tests.
- Source-mode compiles are jailed to `templates/` (`--root`); imports outside `/typst/` are rejected at the API layer too.
- Port 8000 is occupied by something else on this machine — the app standardizes on **8011**.
- Werkzeug-format password hashes are implemented in `backend/app/security.py` for legacy account compatibility — don't swap the format.
- A Gemini key was leaked in OLD git history (both GitHub remotes) and was still live as of 2026-06-13 — rotate it and use fresh keys only.
