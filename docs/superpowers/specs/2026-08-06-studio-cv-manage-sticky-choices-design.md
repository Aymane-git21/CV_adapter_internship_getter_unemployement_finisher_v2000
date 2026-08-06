# Studio: saved-CV inspect/delete + sticky launch choices

Date: 2026-08-06. Autonomous session; design decisions documented here in place of interactive brainstorming.

## Request

1. In the studio, let the user check the data saved from their CVs by clicking the CV box, and delete a saved CV via a small x that appears on hover.
2. When the user presses Tailor CV, register all choices so the next visit preselects them.

## Scope

All UI work lands in `frontend/src/pages/Studio/NewJobPanel.tsx`. Backend already ships everything needed:

- `GET /api/cvs` returns full parsed `CVData` per saved CV (`MasterCVMeta.data`).
- `DELETE /api/cvs/{id}` exists with ownership checks (`backend/app/routers/cvs.py:144`).
- No FK from documents to master_cvs: CV data is copied into jobs at generate time, so deleting a saved CV can never break an existing or running job.

Backend change: none. Backend tests: added (`backend/tests/test_cvs.py`) to pin the DELETE contract the UI now depends on.

## Feature 1: inspect + delete

**Inspect.** Clicking a saved-CV chip selects it and opens an inspector panel under the chip row showing the parsed data: name, headline, contacts, summary, experience, education, skills, projects, languages, certifications, interests. Empty sections are hidden. Clicking the already-selected chip toggles the inspector. The panel has its own close button and a max-height scroll.

**Delete.** A small x sits in the chip's top-right corner, hidden until hover or keyboard focus (`group-hover` / `group-focus-within`, same pattern as the job-tab close button). Clicking it calls `api.deleteCv` directly, no confirm dialog, per the request. After delete:

- list refreshes locally (no refetch),
- if the deleted CV was selected, selection falls back to the default CV, else the first remaining,
- if none remain, CV source flips to paste mode,
- inspector closes if it showed the deleted CV.

Settings keeps its existing management UI; this adds the same capability where the user actually is.

**Rejected alternative:** a two-step inline confirm on the x. The request says click deletes. The chip list mirrors Settings, where delete is also one click.

## Feature 2: sticky launch choices

**What gets saved:** language, rewrite intensity, template, accent, compiler, CV source mode, selected saved-CV id, save-as-master checkbox. Not saved: job descriptions (content, not a choice) and photo (file upload, not restorable).

**When:** at the moment Tailor CV is pressed, before the API call. The press is the registration event; a server-side failure does not unregister the choice.

**Where:** localStorage, versioned key `cvg_launch_prefs.v1`, same vanilla pattern as `cvg_open_jobs` in `store.ts`. Works for guests and authed users. Per-browser, not per-account, matching the existing byok-key and open-tabs behavior.

**Restore:**

- Fields with static domains (language, intensity, accent, saveMaster, cvMode) validate at load and feed lazy `useState` initializers.
- Template and compiler depend on async `config` + `me`: restored raw, then a one-shot effect downgrades them once entitlements arrive (unknown or locked template -> onyx; latex without entitlement, latex disabled, or non-onyx template -> typst). One-shot so a later `refreshMe` never clobbers in-session edits.
- Saved-CV id restores inside the existing cvs-fetch effect only if that id still exists; else default-or-first as today.

**Rejected alternative:** server-side per-user prefs. Cross-device sync was not asked for, guests could not use it, and it adds a table + endpoints for a preference that is cosmetic. localStorage is the vanilla solve.

## Failure modes, walked

1. Delete last CV while selected: source flips to paste, launch stays gated until text is pasted.
2. Delete mid-running job: impossible to break; jobs own copied data (no FK).
3. Stored template locked after plan change: one-shot effect resets to onyx, accent keeps the user's stored color.
4. localStorage unavailable (private mode): all reads/writes wrapped, feature silently off.
5. Corrupt/stale stored JSON: parse guarded, invalid fields fall back per-field, not whole-blob.
6. Two tabs: last press wins. Harmless.
7. Chip x on touch devices: no hover, but chips are focusable; x also shows on focus-within. Settings remains the fallback surface.

## Tests

- `backend/tests/test_cvs.py`: delete removes from list; cross-user delete 404s; double delete 404s; deleting the default leaves the list servable.
- `frontend/src/__tests__/launchPrefs.test.ts`: round-trip, per-field fallback on invalid values, corrupt JSON, version isolation, storage-off no-op.
- i18n parity test picks up the new keys in en/fr/de automatically.
- Eval suite: not applicable, no LLM surface in either feature (gate-test lane only).
