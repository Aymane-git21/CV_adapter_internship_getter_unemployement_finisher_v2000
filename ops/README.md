# CV Glowup CI/CD protocol

One script, [deploy.py](deploy.py), runs the same protocol locally and in GitHub
Actions. Stdlib only, decision logic unit-tested in [tests/test_deploy.py](tests/test_deploy.py).

## The protocol

```
gate ──> candidate ──> smoke candidate ──> promote ──> smoke prod ──> done
tests    --no-traffic   tagged URL,         traffic     public URL
         build, 0 user   0 user traffic     shift        │
         traffic                                         └─ fail? auto-rollback
                                                            to previous revision
```

1. **Gate** — `ruff check backend ops`, `pytest backend/tests`, `pytest ops/tests`,
   `npm run build`. Any red stops the deploy before anything is built.
2. **Preflight** — GCP billing must be enabled (the account self-suspends on
   payment-threshold failures; the script names the fix) and the tracked tree
   must be clean (you deploy commits, not local state).
3. **Candidate** — `gcloud run deploy --source . --no-traffic --tag cand-<sha>`.
   Cloud Build builds the image; the new revision comes up with **zero traffic**.
   Users still hit the old revision. A failed build changes nothing.
4. **Smoke the candidate** on its private tagged URL
   (`https://cand-<sha>---cvglowup-….a.run.app`), with retries for cold start:
   - `GET /api/healthz` → 200, `db: true` (real `SELECT 1` against Postgres)
   - `GET /api/config` → 200, `ai_mode == "gemini"`, templates + free/plus/pro plans present
   - `GET /` → 200, SPA root div present (frontend made it into the image)
   Failure = candidate rejected, prod untouched, exit 1.
5. **Promote** — `update-traffic --to-revisions <new>=100`. Cloud Run shifts
   atomically; in-flight requests on the old revision complete. Zero downtime.
6. **Verify prod** — same smoke on the public URL. If it fails, traffic is
   **automatically shifted back** to the previous revision and the deploy exits 1.
7. **Cleanup** — stale `cand-*` tags from earlier deploys are removed.

Smoke checks use `/api/healthz`, not `/healthz`: Google's edge intercepts
`/healthz` on `*.run.app` hosts and answers 404 before the container sees it.

## Commands

```bash
python ops/deploy.py deploy              # full protocol
python ops/deploy.py deploy --no-promote # stop after candidate smoke (manual canary)
python ops/deploy.py rollback            # back to the previous READY revision
python ops/deploy.py rollback --revision cvglowup-00010-hmk
python ops/deploy.py promote --revision cvglowup-00011-xyz
python ops/deploy.py smoke               # smoke prod right now
python ops/deploy.py status              # who is serving, traffic, tags
python ops/deploy.py gate                # tests only
```

Rollback needs no build: old revisions stay deployed, traffic just moves back.
It finishes in seconds and is itself smoke-checked.

## GitHub Actions

- [deploy.yml](../.github/workflows/deploy.yml) — manual dispatch or `v*` tag.
  Job 1 `gate` runs the tests, job 2 runs `deploy.py deploy --skip-gate`.
  Needs repo **variable** `GCP_PROJECT_ID` and **secret** `GCP_SA_KEY`
  (setup in [docs/deploy.md](../docs/deploy.md)).
- [rollback.yml](../.github/workflows/rollback.yml) — manual dispatch, optional
  revision input.
- Both share a `deploy-cvglowup` concurrency group so a deploy and a rollback
  can never race each other.

## Configuration is code

`deploy.py` passes the **complete** env/secret/resource set on every deploy
(`ENV_VARS`, `SECRETS`, `MEMORY`, … at the top of the script). Anything added
by hand with `gcloud run services update` is wiped on the next deploy — change
the script instead. `test_deploy_args_keeps_vertex_config` pins the Vertex AI
routing (`GEMINI_USE_VERTEX=1`) so it can never fall out silently again.

## Failure modes, walked

| Failure | What happens |
|---|---|
| Tests red | Deploy never starts. |
| Billing suspended (past-due gotcha) | Preflight aborts with the fix named. |
| Cloud Build fails | No new revision; prod untouched. |
| Candidate unhealthy (bad secret, broken DB URL, missing frontend) | Smoke on tagged URL rejects it; prod never saw it. |
| Prod smoke fails after promote | Auto-rollback to the recorded previous revision, then prod is smoke-checked again. |
| Bug found hours later | `python ops/deploy.py rollback` or the Rollback workflow: seconds, no build. |
| Deploy + rollback triggered concurrently | Actions concurrency group serializes them. |
