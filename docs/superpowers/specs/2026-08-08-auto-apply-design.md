# Auto-Apply Pipeline — Design

Date: 2026-08-08
Status: approved in session (review queue + France-first confirmed by Ayman)
Scope of this spec: Phases 1 and 2. Phases 3-5 get their own spec when reached.

## Problem

Today the studio is manual at both ends: the user finds postings themselves, pastes them in, and after generation applies by hand. Target state: postings arrive automatically for a saved search (first: Ayman's own search, Toulouse, France), every posting gets its documents and screening answers pre-generated on demand, and applications go out from a review queue with one approval click. First user is Ayman (live dogfood); it ships publicly later behind Pro/BYOK gating.

Outcome metric: applications sent per week, and minutes from posting-arrival to sent. Both logged per pipeline transition; a weekly count query makes the number visible.

## Locked decisions

1. **Review queue, not autopilot.** Every send is individually approved by the user. No unattended submissions.
2. **France-first.** France Travail (ex-Pôle emploi) official API is the primary source; Adzuna FR is backfill. Toulouse + radius is the first saved search.
3. **No third-party passwords, ever.** No LinkedIn/Indeed/StepStone credentials are collected or stored, in any phase. Logged-in platforms are reached only via the phase-3 browser extension running in the user's own session.
4. **No server-side scraping of bot-defended boards.** Server code touches only official APIs and, in phase 3+, public no-login ATS forms.
5. **Email applications send from the user's own mailbox** (Gmail OAuth `gmail.send`), never from a cvglowup.com address. Dev fallback: write RFC 5322 `.eml` files to disk for manual sending.

## v1 scope (phases 1 + 2)

- **Saved searches**: keywords, location (INSEE commune code + radius km, Toulouse = 31555 to verify at kickoff), contract type, seniority. CRUD in Settings.
- **Poller**: scheduled fetch per saved search. Dev: asyncio loop in the backend. Prod: Cloud Scheduler hitting an OIDC-protected internal endpoint.
- **Dedup**: source + external_id unique key, plus fuzzy (title, company) hash to catch cross-source duplicates. Idempotent re-polls.
- **Inbox**: new postings land as `inbox` items in a new Pipeline tab in the studio. Nothing auto-generates on arrival (protects quota and BYOK spend).
- **Generation**: from the inbox, single or bulk trigger runs the existing batch pipeline per posting. New fourth artifact: **screening answers** (see Answers engine). Existing three stay: tailored CV, lettre de motivation, outreach message.
- **States**: `inbox → generated → approved → sent → replied | rejected`. The board doubles as the job tracker the product lacked.
- **Apply, email route**: postings that advertise an application email get a compose view: outreach message as body, CV + LM PDFs attached, editable before approve. Approve = send via Gmail API.
- **Apply, link route (v1)**: postings pointing at an external ATS open the link with all artifacts one click from copy. Autofill is phase 3.
- **Caps and audit**: hard per-day send cap (default 15, configurable), append-only audit log of every transition and send.

## Answers engine

- **FactsProfile** per user: work permit status, notice period, salary range, mobility/relocation, languages, driving licence, availability date. Editable in Settings.
- Fixed-fact questions are answered deterministically from FactsProfile (string mapping, no model call).
- Free-text questions go to Gemini grounded in master CV + posting + FactsProfile, with an explicit no-invented-facts instruction. Same provider abstraction as existing generation (fake provider support included for offline dev).

## Architecture

```
backend/app/sources/__init__.py     SourceAdapter protocol + registry
backend/app/sources/france_travail.py   OAuth client-credentials, Offres d'emploi v2
backend/app/sources/adzuna.py           app_id/app_key, what/where params
backend/app/mailer.py               Gmail API send w/ attachments; .eml fallback
backend/app/routers/applications.py saved searches, inbox, generate, approve/send, transitions
backend/app/schemas.py              + JobPostingIn/JobPosting, FactsProfile, AnswersDoc
backend/app/models.py               + SavedSearch, JobPosting, Application tables
backend/app/jobs.py                 + write_answers task alongside cv/letter/message
frontend/src/pages/Studio/Pipeline* board UI, posting drawer, email compose view
frontend Settings                   FactsProfile editor, saved-search editor
```

- Contract: `JobPosting` (source, external_id, title, company, location, contract_type, description, apply_email nullable, apply_url nullable, posted_at, raw JSON). Adapters normalize into it; nothing downstream knows the source.
- Schema changes go through `_ensure_columns` in `backend/app/db.py` (the repo's one migration path).
- New tables via `create_all`; new columns on existing tables via `_ensure_columns`.
- Feature flag `pipeline_enabled` per user; on for Ayman's account first.
- Config additions: `ft_client_id`, `ft_client_secret`, `adzuna_app_id`, `adzuna_app_key`, `send_cap_daily`, `poll_interval_minutes`, Gmail OAuth scope addition.

## Error handling

- Adapter failures: per-source backoff, poll survives one source being down, errors surface in the Pipeline tab header, never lose already-stored postings.
- Send failures: Application stays `approved` with the error attached; retry is explicit, never automatic; quota-style refund logic not needed (sends are not metered generations).
- Generation failures: existing retry/refund path applies unchanged.
- Rate limits: France Travail enforces per-second caps; adapter throttles and honors Retry-After.

## Tests (gate, deterministic, <2s)

- Source adapters against recorded JSON fixtures (no live HTTP in gate lane).
- Dedup idempotency: same fixture polled twice yields zero new rows.
- State machine: illegal transitions rejected (e.g. inbox → sent).
- Email composer: MIME structure, both attachments present, UTF-8 subject/body, header-injection attempt rejected.
- Deterministic answers fill from FactsProfile.
- Send cap enforcement at the boundary.

## Evals (periodic, paid)

- Answers faithfulness: generated free-text answers vs FactsProfile + master CV; fail on any invented fact. Threshold gate before ship.
- French lettre de motivation quality: existing language harness extended with pipeline-generated samples.
- End-to-end smoke on the fake AI provider: poll fixture → generate → compose → .eml written.

## Out of scope for v1

Browser extension, LinkedIn/Indeed/StepStone automation, Workday assist, auto-generate-on-arrival, multi-user rollout, DOCX export (separate track from the competitive teardown).

## Phase ladder (approved order)

| Phase | Target | Difficulty |
|---|---|---|
| 1 | France Travail API import + Pipeline board | Easiest, official API |
| 2 | Email applications via Gmail + screening answers | Easy, no adversary |
| 3 | Extension: clip postings anywhere (Welcome to the Jungle, APEC, HelloWork, LinkedIn); autofill public ATS forms (Greenhouse, Lever, Teamtailor, Flatchr) | Medium |
| 4 | Indeed.fr and LinkedIn Easy Apply assisted fill, user clicks submit | Hard, hostile platforms |
| 5 | Workday / SuccessFactors portal assist (Airbus, Thales, Safran in Toulouse) | Hardest UX |

## Open items to resolve at phase-1 kickoff

- Register the app on francetravail.io; confirm Offres d'emploi v2 endpoint shapes, auth flow, and rate limits against live docs.
- Verify Toulouse INSEE code and radius parameter semantics.
- Adzuna API key signup (free tier).
- Google OAuth consent screen: add `gmail.send` scope (existing Google sign-in client).
- Measure how many FT postings expose an application email vs external link, to size the phase-2 payoff before building the compose flow.
