---
name: cvglowup-runbook
description: How to run, build, test, and deploy CV Glowup locally (Windows) and on Google Cloud Run. Use when starting dev servers, building the Docker image, deploying, or touching env/config. Documents both the legacy stack and the rehaul target — update as the rehaul lands.
---

# CV Glowup Runbook

## Current (legacy) stack — what exists today

- **Backend**: Flask in `app.py` (~650 lines, everything in one file). Serves the SPA from `static/dist` + JSON API. In-memory `JOBS` dict + `ThreadPoolExecutor` for generation jobs (breaks with >1 gunicorn worker; Dockerfile pins `--workers 1`).
- **Frontend**: React 18 + Vite 5 in `src/`, all inline styles, vanta/three background. Built into `static/dist` by `npm run build`.
- **AI**: deprecated `google-generativeai` SDK, model `gemini-2.5-flash`, prompts ask for raw LaTeX (fragile — see gemini-api skill for the replacement).
- **PDF**: `pdflatex` subprocess. Windows path hardcoded to MiKTeX at `C:\Users\ayman\AppData\Local\Programs\MiKTeX\...`; Docker installs ~3 GB of texlive. Being replaced by Typst (see typst-doc-engine skill).
- **DB**: SQLAlchemy — `DATABASE_URL` (Neon Postgres) > `CLOUD_SQL_CONNECTION_NAME` (Cloud SQL socket) > SQLite in `/tmp`. Schema created via `db.create_all()`, no migrations. `FORCE_DB_RESET=true` drops everything — dangerous, never set in prod.
- **Auth**: flask-login session cookies, email+password.
- Generated files land in `/tmp/outputs` — ephemeral on Cloud Run, lost across instances.

## Run locally (Windows)

```powershell
# Terminal 1 — API (port 8080; vite proxy expects 5000, see gotcha below)
python app.py
# Terminal 2 — frontend with HMR
npm run dev   # http://localhost:5173
```

Gotchas:
- `vite.config.js` proxies `/api`, `/download`, `/view` to `127.0.0.1:5000`, but `app.py` defaults to PORT **8080** — set `$env:PORT='5000'` before `python app.py`, or fix the proxy. (`/start_job` and `/job_status` are NOT in the proxy list — legacy bug if hit via the vite dev server.)
- `.env` must exist with at least `GEMINI_API_KEY` and `SECRET_KEY`. Never commit it.
- Legacy LaTeX compile needs MiKTeX locally; once Typst lands, `winget install Typst.Typst` is the only doc dependency.

## Build & deploy (Google Cloud Run)

```powershell
npm run build                                  # → static/dist
docker build -t cvglowup .                     # multi-stage: node build → python runtime
gcloud run deploy cv-tailor-app --source . --region europe-west1 --allow-unauthenticated
```

- Secrets go in **Secret Manager**, referenced via `--set-secrets` — never `--set-env-vars` for keys, and never in tracked docs (this bit us once already).
- Required env in prod: `GEMINI_API_KEY`, `SECRET_KEY`, `DATABASE_URL` (Neon) or Cloud SQL trio, `ALLOWED_ORIGINS=https://cvglowup.com,https://www.cvglowup.com`.
- Domains: cvglowup.com / www.cvglowup.com mapped to the Cloud Run service.

## Rehaul target (keep current as phases land)

- Backend → FastAPI (async) + `google-genai` SDK + structured outputs; job state in Postgres (works with any worker count + autoscaling), progress via SSE; artifacts in GCS with signed URLs (or DB bytea while small).
- Docs → Typst end-to-end; in-browser live preview via typst.ts WASM; server compile with the typst binary (Docker image ~200 MB, cold start seconds not tens of seconds).
- Frontend → React + TypeScript + Tailwind, studio layout (editor | live preview), multi-job tabs, chat editing.
- Billing → Stripe Checkout + webhooks; quotas enforced server-side per plan; BYO-key bypasses platform quota.
- CI/CD → GitHub Actions: lint+test → docker build → deploy to Cloud Run on main.

## Repo hygiene warnings (as of 2026-06)

- `node_modules/` is committed to git (6,750 files) — `git rm -r --cached node_modules` + add to .gitignore.
- `.gitignore` has a corrupted last line (`master_cv.md* . d b`) — `*.db` is effectively not ignored.
- A real Gemini API key was committed to deployment docs in past git history — treat any key found in docs or history as compromised and rotate it; never put keys in tracked files (use `.env` locally, Secret Manager in prod). Note there are two GitHub remotes (`origin` and `correct`) pointing at different repos with diverged histories.
- A GCP service-account JSON sits untracked in the repo root — keep untracked, prefer deleting it and using `gcloud auth application-default login` / workload identity.
- Root directory is littered with LaTeX build artifacts (*.aux, *.log, *.out, test PDFs) — safe to delete.
