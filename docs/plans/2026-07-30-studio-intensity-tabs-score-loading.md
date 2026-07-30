# Plan: rewrite intensity, panel tabs, score typography, loading screen

Date: 2026-07-30. Scope: four Studio features. Each phase is self-contained and executable in a fresh session. Phases 1 and 2 share a contract defined in Phase 0 and can run in parallel worktrees. Phases 3, 4, 5 are frontend-only and independent of each other, but 2 and 5 both edit `frontend/src/i18n.tsx` and `frontend/src/pages/Studio/index.tsx` is touched only by 5. If run as parallel sessions, let each phase add its own i18n key block and merge; the parity test catches mistakes.

---

## Phase 0: Discovery findings (consolidated, verified 2026-07-30)

### Allowed APIs and patterns (cited, do not invent others)

**Generation request path**
- `frontend/src/pages/Studio/NewJobPanel.tsx:81-92` builds the payload (`job_descriptions, master_cv_id, cv_text, language, template, accent, show_photo, photo_id, save_master`) and calls `api.generate(body)`.
- `frontend/src/api.ts:177-181` `api.generate` with an inline body type (no named interface). `request()` at 117-139 handles BYOK header + `ApiError`.
- `backend/app/schemas.py:181-190` `GenerateIn` pydantic model. House enum idiom is plain `str` + comment + runtime whitelist (`schemas.py:123` `density: str = "normal"  # normal | tight | xtight`; `generate.py:85` language whitelist with silent fallback). There is NO `Literal`/`Enum` field anywhere in `backend/app`.
- `backend/app/routers/generate.py:26-46` handler; `100-104` calls `spawn_job(jid, master_data, body.photo_id, body.template, body.accent, body.show_photo, byok, guest_hash=guest_hash)`.
- `backend/app/jobs.py:69-78` `spawn_job`, `:85` `_run_job_safely(*args)` forwards POSITIONALLY, `:93-102` `_run_job`, `:126-135` `_pipeline`, `:154` `provider.tailor_cv(job.job_description, analysis, master, language)`.
- `backend/app/ai/base.py:21` protocol `tailor_cv(self, jd, analysis, master, language) -> CVData`.
- `backend/app/ai/gemini.py:138-147` builds `prompts.tailor_cv_prompt(jd, analysis.notes, keywords, master_json, language)`; `_generate` (79-91) sets only `response_mime_type`/`response_schema`, no sampling temperature exists.
- `backend/app/ai/fake.py:91-100` offline provider used by ALL gate tests (`backend/tests/conftest.py:8` sets `CVG_FAKE_AI=1`).
- `backend/app/ai/prompts.py:55` `tailor_cv_prompt(jd, analysis_notes, keywords, master_json, language)`. Rewrite mandate is hardcoded prose: "You are a WRITER, not a copyist" (59-62), TRUTH BOUNDARY (64-72), HARD RULES 1-10 (74-99). JD at 103-104, master JSON at 106-107, keywords at 82.

**Panel tabs**
- `frontend/src/pages/Studio/EditorPanel.tsx:35-52` renders Content/Source/Assistant. Button classes (line 43): `px-3 py-2 font-mono text-[11px] uppercase tracking-wider transition-colors`, active `text-text`, inactive `text-text/50 hover:text-text/70`. No CSS class in styles.css targets these tabs; all styling is inline Tailwind.
- Sibling document-kind tabs idiom at `frontend/src/pages/Studio/index.tsx:112-127`: `border-b-2 px-3.5 py-2.5 text-[13px]`, active `border-flame-500 text-text`, inactive `border-transparent text-text/70 hover:text-text`.
- Labels: i18n keys `studio.panel.content|source|chat` (en i18n.tsx:47-49, fr 139-141, de 228-230). De "Quelltext" is the longest label.

**ATS score panel**
- `ScoreCard`, private component in `frontend/src/pages/Studio/Preview.tsx:7-41`, mounted at line 64. Delta span at 16-20 (`font-mono text-[13px]`, literal `→` at line 18, after-value `font-semibold text-ok-400`). Missing chips at 26-30: `rounded-full border border-signal-500/25 bg-signal-950 px-2 py-0.5 font-mono text-[10.5px] text-danger`, `missing.slice(0, 5)` + `+N` overflow. Empty state line 36 `font-mono text-[11px] text-ok-400`. Title uses `.eyebrow` (styles.css:84-89).
- Data: `DocumentPayload.score_before/score_after/keywords` (api.ts:58-61) from `GET /api/documents/{id}`; computed deterministically in `backend/app/ats.py:32-47`, stored in `jobs.py:213-214`.
- i18n: `studio.score.title|missing|none` used; `studio.score.before|after` exist but are UNUSED.

**Loading/progress**
- Transport is SSE: `api.ts:204-215` `jobEvents` EventSource, closes on terminal status. `store.ts:127-134` `watchJob` writes each `JobSnapshot` into `jobs`. "Loading" = `status === "queued" | "running"`, no boolean flags in the store.
- `frontend/src/pages/Studio/index.tsx:199-209` routes: `ProgressView` replaces the workspace for the generating TAB only (43-73: pct bar from last event, event log rows, `AdSlot slot="studio-progress"` at 69). Tab strip stays live; other tabs remain editable; `+` opens NewJobPanel for parallel launches. Nothing global is blocked today.
- Backend emits (jobs.py): `analyze` pct 8 (line 141), `analyzed` (148), `generate` pct 30 (153), `generated` (160), `render` pct 72 (179), `done` pct 100 (231), `failed` pct 100 (115, 123). Messages are hardcoded English.
- The only overlay pattern: `components/AuthModal.tsx:84-94`. Reusable CSS: `.glass-panel` (styles.css:70-76), `.sheet` (203-215), `.btn-flame` (100-129), `.eyebrow` (84-89). `prefers-reduced-motion` kill-switch at 229-236. NO skeleton/shimmer/overlay/spinner classes exist; all spinners are lucide `Loader2` + `animate-spin`.

**Cross-cutting**
- i18n: flat `dict` in `frontend/src/i18n.tsx` (`en` from line 4, `fr` from 100, `de` from 189, `as const` at 278). Add every new key to ALL THREE blocks; `frontend/src/__tests__/i18n.test.ts` enforces key parity. `t()` takes a key only, no interpolation.
- Fonts loaded (index.html:17): Bricolage Grotesque (landing-only, `.forge-display`), JetBrains Mono (`--font-mono`), Plus Jakarta Sans (`--font-sans`, app body). IBM Plex @fontsource imports in main.tsx:1-9 are dead weight (referenced by nothing).
- Segmented-control pattern to copy: `NewJobPanel.tsx:132-135` (`seg` helper) + language segment at 276-284 (`inline-flex gap-1 rounded-lg border border-black/10 glass-panel p-1`). Card-option pattern with descriptions: template picker at 288-312 (selected `border-flame-500 bg-flame-950`).
- Tests: frontend `npm test` (vitest, node env, no jsdom, no component tests possible without new deps); backend `python -m pytest` from `backend/` (pyproject `testpaths=["tests"]`, asyncio auto, `CVG_FAKE_AI=1` via conftest). Prompt pins in `backend/tests/test_prompts.py:9-24` call `tailor_cv_prompt` with 5 POSITIONAL args. Paid eval: `backend/evals/eval_tailor_boost.py` with deterministic thresholds in `backend/evals/metrics.py`.

### Contract locked for Phases 1 and 2

- Field name: `rewrite_intensity`. Values: `"reshape" | "minor" | "major" | "max_ats"`. Default: `"major"` (current prompt behavior, so existing users see no change).
- Validation: house idiom. `GenerateIn.rewrite_intensity: str = "major"  # reshape | minor | major | max_ats`, whitelist fallback in the route like language at generate.py:85.
- Scope: modulates `tailor_cv` only. Letter and outreach prompts unchanged (deliberate non-goal).
- Persistence: pass-through like `template`/`accent`; NOT stored on `Job` (no settings column exists; adding one is out of scope).
- Truth boundary applies at every level including `max_ats`. UI copy must not promise a literal 100% score: coverage is capped by what the master CV truthfully supports, and the missing-chips panel shows the remainder.

### Anti-pattern guards (global)

- Do not add pydantic `Literal`/`Enum` (none exist; house style is str + whitelist).
- Do not set Gemini sampling temperature; the "temperature" feature is a prompt-mandate switch, not a sampling knob.
- Do not touch `--forge-*` vars or `.forge` scope for Studio UI (landing-only dark register).
- Do not invent `--radius-*` tokens, `.tab`/`.modal`/`.skeleton` classes (they do not exist; add new classes only where this plan says so).
- Do not build on the vestigial `@fontsource/ibm-plex-*` imports.
- Do not add a global overlay for generation; parallelism lives on the tab strip and must stay.
- `_run_job_safely(*args)` forwards positionally: thread the new param through `spawn_job`, `_run_job`, `_pipeline` identically, inserted BEFORE `guest_hash`.
- Keep `tailor_cv_prompt`'s new param keyword-with-default so the two existing positional pin tests keep passing.

---

## Phase 1: Backend `rewrite_intensity` (backend only)

### What to implement

1. `backend/app/schemas.py` (GenerateIn, 181-190): add `rewrite_intensity: str = "major"  # reshape | minor | major | max_ats`. Copy the comment idiom from `density` (schemas.py:123).
2. `backend/app/routers/generate.py`: normalize after line 85, copying the language idiom:
   `intensity = body.rewrite_intensity if body.rewrite_intensity in ("reshape", "minor", "major", "max_ats") else "major"`, then pass `intensity` into `spawn_job` (call at 100-104), inserted before `guest_hash`.
3. `backend/app/jobs.py`: add `rewrite_intensity: str = "major"` before `guest_hash` in `spawn_job` (69-78), `_run_job` (93-102), `_pipeline` (126-135); forward to the `tailor_cv` call at line 154.
4. `backend/app/ai/base.py:21`: extend the protocol: `tailor_cv(self, jd, analysis, master, language, intensity: str = "major")`.
5. `backend/app/ai/gemini.py:138-147`: accept `intensity`, forward to `prompts.tailor_cv_prompt(..., intensity=intensity)`.
6. `backend/app/ai/fake.py:91-100`: accept `intensity`. When `"reshape"`, return the master untouched except the deterministic "Key match" skill group; otherwise keep current behavior (summary prefix rewrite). This makes plumbing assertable offline.
7. `backend/app/ai/prompts.py`: add `intensity: str = "major"` as a KEYWORD param on `tailor_cv_prompt` (line 55). Introduce `_INTENSITY_MANDATES: dict[str, str]` and interpolate the selected mandate where the "You are a WRITER, not a copyist" block sits (59-62). Levels:
   - `reshape`: do not rewrite wording; reorder sections/bullets, group skills, trim redundancy, minimal grammar fixes only.
   - `minor`: keep most phrasing; reorder for relevance, tighten wording, surface skills already present that match the role; no restructuring of roles, no new bullets.
   - `major`: the current mandate text, verbatim (this is the default; prompt output for `major` must remain byte-identical to today so existing pins hold).
   - `max_ats`: current mandate plus an addendum: every keyword from the list that the master CV truthfully supports must appear verbatim or via its standard alias; mirror the job post's terminology; retitle skill groups to standard names. TRUTH BOUNDARY (64-72) stays verbatim in ALL levels; a keyword with no support in the master must not appear.

### Tests (same commit)

- `backend/tests/test_prompts.py`: keep the two existing pins green (they call with 5 positional args; the default must reproduce today's prompt). Add pins: `"not a copyist"` present for `major` and `max_ats`; reshape mandate marker present ONLY for `reshape`; truth-boundary line present in all four; verbatim-keyword mandate present ONLY in `max_ats`.
- `backend/tests/test_api.py`: extend a `/api/generate` payload with `rewrite_intensity` (copy `test_full_flow`, 41-45); add a bad-value case asserting silent fallback (job completes, no 422), copying `test_validation_errors` (140-150) structure for the payload shape.
- New FakeProvider unit assertions: `tailor_cv(..., intensity="reshape")` leaves the summary unchanged; default rewrites it.

### Eval (same commit)

- Extend `backend/evals/eval_tailor_boost.py` to run `reshape`, `major`, `max_ats` and assert orderings with the existing deterministic metrics (`backend/evals/metrics.py`): novelty(reshape) < novelty(major) <= novelty(max_ats); ATS after-score(max_ats) >= after-score(major) >= after-score(reshape). Reuse fixture `backend/tests/fixtures/sample_cv.json`.

### Verification checklist

- `cd backend && python -m pytest -q` green.
- `grep -rn "rewrite_intensity" backend/app` hits schemas, router, jobs, base, gemini, fake, prompts (7 files).
- `grep -n "Literal\|import enum" backend/app` shows no new hits.
- Manual: `tailor_cv_prompt(jd, notes, kws, mj, "en")` equals today's output (pin test covers this).

---

## Phase 2: Frontend intensity picker (frontend only, contract from Phase 0)

### What to implement

1. `frontend/src/pages/Studio/NewJobPanel.tsx`:
   - State near lines 43-47: `const [intensity, setIntensity] = useState<"reshape" | "minor" | "major" | "max_ats">("major");`
   - Payload (81-91): add `rewrite_intensity: intensity`.
   - UI in the right aside (after the language block at 276-284): copy the language segmented control verbatim (wrapper `inline-flex gap-1 rounded-lg border border-black/10 glass-panel p-1`, buttons via the `seg` helper at 132-135) with the four levels, plus a caption `<p>` under it (`text-[12px] text-text/60`) showing the selected level's description. Title uses `<p className="eyebrow mb-3">{t("studio.intensity.title")}</p>` like line 276. If four segments overflow the aside width (check de labels), fall back to the template-picker card pattern (288-312) instead; decide in-browser, not by guess.
2. `frontend/src/api.ts:177-181`: add `rewrite_intensity?: "reshape" | "minor" | "major" | "max_ats"` to the inline body type.
3. `frontend/src/i18n.tsx`: add to en (studio block near 38-50), fr (near 130-146), de (near 219-235), all three:
   - `studio.intensity.title`: "Rewrite intensity" / "Intensité de réécriture" / "Umschreibungsgrad"
   - `studio.intensity.reshape`: "Reshape" / "Remise en forme" / "Nur Struktur"
   - `studio.intensity.minor`: "Minor changes" / "Retouches légères" / "Kleine Änderungen"
   - `studio.intensity.major`: "Major rewrite" / "Réécriture majeure" / "Große Überarbeitung"
   - `studio.intensity.max_ats`: "Max ATS score" / "Score ATS maximal" / "Maximaler ATS-Score"
   - `studio.intensity.reshape.desc`: "Original wording stays; only structure and format change." / "Les formulations restent; seule la structure change." / "Formulierungen bleiben erhalten; nur Aufbau und Format ändern sich."
   - `studio.intensity.minor.desc`: "Light touch: reorder, trim, surface matching skills." / "Retouches: réorganise, condense, met en avant les compétences existantes." / "Leichte Eingriffe: umsortieren, kürzen, passende Skills hervorheben."
   - `studio.intensity.major.desc`: "Bullets rewritten around the job's priorities. Facts stay untouched." / "Les points sont réécrits selon les priorités de l'offre. Les faits restent inchangés." / "Punkte werden entlang der Stellen-Prioritäten neu formuliert. Fakten bleiben unverändert."
   - `studio.intensity.max_ats.desc`: "Highest keyword coverage the facts allow." / "Couverture de mots-clés maximale, sans rien inventer." / "Höchste Keyword-Abdeckung, ohne etwas zu erfinden."
   Match the surrounding de register (check neighboring strings for Sie/du before finalizing). No interpolation; `t()` takes keys only.

### Verification checklist

- `cd frontend && npm test` green (i18n parity picks up the 9 new keys in all three blocks).
- `npm run build` green.
- Browser (launch per cvglowup-runbook): picker renders in the New Job aside, caption switches per level, de labels fit; DevTools network shows `rewrite_intensity` in the POST /api/generate body; generation completes end to end.

### Anti-pattern guards

- No shared SegmentedControl component exists; inline the classes or copy the local `seg` helper. Do not create a components/ primitive for this one use.
- Do not gate any level behind plan tiers unless asked (the template picker's `Lock` idiom exists but is not part of this feature).

---

## Phase 3: Panel tab switcher restyle (one file)

### What to implement

`frontend/src/pages/Studio/EditorPanel.tsx:35-52` only. Replace the button classes (line 43) so the tabs read as primary UI in Plus Jakarta Sans instead of 11px uppercase mono:

- From: `px-3 py-2 font-mono text-[11px] uppercase tracking-wider transition-colors` + active `text-text` / inactive `text-text/50 hover:text-text/70`
- To: `border-b-2 px-3.5 py-2.5 text-[13px] font-semibold transition-colors` + active `border-flame-500 text-text` / inactive `border-transparent text-text/60 hover:text-text`

This copies the document-kind tabs idiom at `index.tsx:112-127` (same family, weight up one step), so the two tab rows in the Studio share one visual language. Keep `role="tablist"`/`role="tab"`/`aria-selected` exactly as they are. Keep the syncing spinner (line 51). No styles.css change, no i18n change.

Rationale for the font choice: Plus Jakarta Sans at 600 is the app's existing emphasis face (`.eyebrow`); Bricolage Grotesque is deliberately landing-only (`.forge-display`, styles.css:259-264) and would break the light-shell register. Do not introduce a new font for this.

### Verification checklist

- Browser: Content/Source/Assistant visibly dominant, active tab underlined flame, hover states work, de "Quelltext" does not wrap, `syncing` spinner still aligned.
- `npm run build` green.

---

## Phase 4: ScoreCard typography (one file)

### What to implement

`frontend/src/pages/Studio/Preview.tsx:7-41` only. Move the panel off 10.5px mono onto the app sans, bigger and heavier:

1. Delta span (16-20): `font-mono text-[13px]` becomes `text-[15px] font-semibold tabular-nums`; keep `text-text/50` on the before-value and arrow, keep `text-ok-400` on the after-value (bump it to `font-bold`). The literal `→` stays.
2. "Still missing" label (line 24 area): mono 10.5 uppercase becomes `text-[12px] font-semibold text-text/60` (normal case, no tracking-wider).
3. Keyword chips (26-30): `font-mono text-[10.5px]` becomes `text-[12px] font-medium`; keep `rounded-full border border-signal-500/25 bg-signal-950 px-2 py-0.5 text-danger` and the `slice(0, 5)` + `+N` overflow.
4. Empty state (line 36): `font-mono text-[11px]` becomes `text-[12px] font-medium`.

No styles.css change (`tabular-nums` is a stock Tailwind utility). No i18n change (`studio.score.*` keys already exist; the unused before/after keys stay unused).

### Verification checklist

- Browser with a completed CV job: percentages align (tabular-nums), chips readable at arm's length, fr/de labels fit on one wrapped row, `+N` overflow still renders past 5 keywords, empty state ("All key terms covered") renders in green sans.
- `npm run build` green.

---

## Phase 5: Loading screen upgrade (per-tab, parallelism preserved)

### What to implement

Redesign `ProgressView` in `frontend/src/pages/Studio/index.tsx:43-73`. It stays scoped to the generating tab (routing at 199-209 unchanged), so the tab strip, other tabs, and the `+` launcher keep working during generation. Explicitly NOT a global overlay.

1. **Staged checklist** replacing the raw event log. Fixed stages mapped from the SSE `step` field (contract from jobs.py): `analyze`/`analyzed` = stage 1, `generate`/`generated` = stage 2, `render` = stage 3, `done` = stage 4. Row states: completed (CheckCircle2, `text-ok-400`), active (Loader2 `animate-spin text-primary`), pending (dot, `text-text/30`). Stage labels from new i18n keys; render the latest `event.message` as a one-line detail under the active stage (server messages are English and carry dynamic detail; they are the caption, not the label).
2. **Skeleton preview sheet** beside or under the checklist: one `.sheet` div at `aspect-[1/1.414]` (copy Preview.tsx:114-116) containing 6 to 8 grey bars with a shimmer sweep. Add to `frontend/src/styles.css`: a `@keyframes shimmer` and a `.skeleton-shimmer` class (gradient sweep on `background-position`). The existing `prefers-reduced-motion` kill-switch (styles.css:229-236) already zeroes animation durations globally; confirm it covers the new keyframes.
3. **Progress bar**: keep the existing pct bar (index.tsx:52-56 idiom, `Math.max(4, pct)`, 700ms transition), add a right-aligned `{pct}%` in `text-[12px] font-semibold tabular-nums text-text/60`.
4. Keep `<AdSlot slot="studio-progress" />` (line 69).
5. i18n keys (en/fr/de, all three blocks):
   - `studio.progress.title`: "Forging your documents" / "Vos documents sont en cours de création" / "Ihre Dokumente entstehen"
   - `studio.progress.analyze`: "Reading the job post" / "Lecture de l'offre" / "Stellenanzeige wird gelesen"
   - `studio.progress.generate`: "Writing CV, letter and outreach" / "Rédaction du CV, de la lettre et du message" / "CV, Anschreiben und Nachricht werden verfasst"
   - `studio.progress.render`: "Typesetting" / "Mise en page" / "Satz läuft"
   - `studio.progress.done`: "Ready" / "Prêt" / "Fertig"
   - `studio.chat.busy`: "editing…" / "modification…" / "Bearbeitung…" and use it in `ChatPanel.tsx:84` to replace the hardcoded "editing…" (discovery found this i18n gap; one-line rider).
6. Unknown/future step values must not break the mapping: default any unrecognized step to the highest stage already reached.

### Verification checklist

- `npm test` green (parity for the 6 new keys), `npm run build` green.
- Browser: launch a generation; stages tick through analyze, generate, render, done; shimmer visible; pct label counts up; DURING the run, switch to another tab and edit a document, then press `+` and open the New Job panel (parallelism proof); on completion the tab flips to the workspace by itself; a failed job still shows `FailedView`.
- Reduced-motion check: `resize_window`/emulation or OS setting, shimmer and spinners stop.

### Anti-pattern guards

- No `.modal`/full-page overlay; the AuthModal pattern is for auth only.
- Do not poll `api.job()`; SSE via the existing `watchJob` is the only transport.
- Do not translate server event messages by string-matching them; map on the `step` key.

---

## Phase 6: Final verification (after all phases merge)

1. `cd backend && python -m pytest -q` and `cd frontend && npm test && npm run build`.
2. Anti-pattern greps: `grep -rn "Literal\[" backend/app` (empty), `grep -rn "temperature" backend/app/ai` (empty), `grep -n "font-mono" frontend/src/pages/Studio/Preview.tsx` (empty), `grep -n "editing…" frontend/src/pages/Studio/ChatPanel.tsx` (empty).
3. End-to-end in the browser (per cvglowup-runbook, `CVG_FAKE_AI=1` for keyless dev): paste a JD, pick `max_ats`, generate; new loading screen runs; on completion the ScoreCard shows the new typography; switch tabs mid-run to prove parallelism; check all three languages via the nav switch.
4. Paid eval lane (needs a real key, run before ship, not in gates): `python backend/evals/eval_tailor_boost.py` with the intensity matrix; confirm the ordering assertions pass.
5. Commit discipline: tests and evals land in the same commits as the features (Phases 1 to 5 each carry their own).

## Deliberate non-goals (flagged, not forgotten)

- Intensity does not modulate letter/outreach prompts and is not persisted on `Job` (no settings column exists; re-run/chat awareness of intensity is a separate decision).
- No Gemini sampling-temperature knob.
- No plan-tier gating of intensity levels.
- FailedView's fake "retry" (closes the tab, index.tsx:203) and the dead IBM Plex @fontsource imports (main.tsx:1-9) are separate cleanups, spawned as background task chips.
