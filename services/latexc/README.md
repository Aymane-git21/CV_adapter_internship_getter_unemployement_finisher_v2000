# latexc — warm LaTeX compile service

CLSI-style (Overleaf) compile service: one long-lived sandboxed container,
per-document compile dirs that persist between requests, so recompiles reuse
latexmk's aux/.fdb state and never start from zero. The backend renders
CVData to `.tex` (backend/app/texsvc/) and sends it here; this service is a
dumb, hardened compiler and knows nothing about CVs.

## Contract (v1)

`contract.py` is the single source of truth, imported by the backend as
`services.latexc.contract` and inside the container as `latexc.contract`.

- `POST /v1/compile` `LatexCompileIn` -> `LatexCompileOut` (pdf + per-page
  SVGs via pdftocairo, `cache: hit|warm|cold`, `timings_ms`, capped
  `log_tail` + `error_line`)
- `DELETE /v1/project/{doc_id}` clears one document's compile dir
- `GET /v1/status` health + cache stats. NEVER route `/healthz` (Google's
  edge intercepts that path on `*.run.app`).
- Auth: `Authorization: Bearer $LATEXC_TOKEN` on every route.

## Hardening

latexmk runs with `-no-shell-escape`, `openin_any=p` / `openout_any=p`,
HOME/TEXMF* jailed to the project dir, process-group kill on timeout
(default 40 s, max 60 s), flat file names only (`^[A-Za-z0-9._-]{1,64}$`),
max 16 files / 4 MB per request, 20 KB log tails. Fonts (IBM Plex, same
files as the Typst preview) are baked into the image; no network is needed
at compile time.

## Warmth model

- Boot prewarm: `probe.tex` compiles on startup, so the first real compile
  after any deploy/scale-up is warm.
- Per-doc cache: `$COMPILE_ROOT/<doc_id>/` holds aux files + last outputs.
  Identical input -> `cache: hit` (no TeX run). Same doc, new content ->
  `cache: warm`. LRU eviction beyond `LATEXC_MAX_PROJECTS` (40) or
  `LATEXC_MAX_TOTAL_MB` (512).
- On Cloud Run, `/tmp` is in-memory: the cache budget counts against
  instance memory (2 GiB).

## Local dev (Docker Desktop)

```bash
docker compose -f services/latexc/compose.yml up -d --build
docker compose -f services/latexc/compose.yml exec latexc python -m pytest /srv/latexc/tests -q
curl -s -H "Authorization: Bearer dev-token" http://localhost:8021/v1/status
docker compose -f services/latexc/compose.yml down   # the manual off-switch
```

Backend `.env` to point at it: `LATEXC_URL=http://localhost:8021`,
`LATEXC_TOKEN=dev-token`.

## Production (Cloud Run)

Deployed and controlled by `ops/latexc.py` (build via `cloudbuild.yaml`,
candidate -> smoke -> promote, plus `on` / `off` / `status`). `off` sets
min-instances to 0: that is the manual off-switch. `POST /api/latex/warmup`
on the backend flips min-instances to 1 when a user enables the LaTeX
compiler. Env: `LATEXC_TOKEN` (Secret Manager), optional
`LATEXC_CONCURRENCY` (default 2).

## Env vars

| var | default | meaning |
|---|---|---|
| `LATEXC_TOKEN` | (required) | bearer token; refuses to serve without it |
| `COMPILE_ROOT` | /tmp/compiles | project cache root |
| `LATEXC_CONCURRENCY` | 2 | max concurrent TeX processes |
| `LATEXC_MAX_PROJECTS` | 40 | LRU cap on cached project dirs |
| `LATEXC_MAX_TOTAL_MB` | 512 | LRU cap on total cache size |
| `PORT` | 8080 | listen port |

## Measured numbers

Fill in after the first container build/test run (see phase 4 validation in
docs/plans/2026-07-30-page-mode-and-latex-compiler.md): image size, cold vs
warm vs hit `timings_ms` for the probe CV.
