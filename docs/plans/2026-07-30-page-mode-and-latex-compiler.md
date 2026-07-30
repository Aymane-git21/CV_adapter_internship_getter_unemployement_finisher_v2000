# Plan: page mode (continuous single page vs A4) + LaTeX compiler with a warm compile service

Date: 2026-07-30. Scope: two per-document features.

1. **Page mode**: a per-document option that renders the CV as one endless auto-height page ("continuous") or keeps the current A4 pagination ("paged", default, unchanged behavior).
2. **LaTeX compiler**: a per-document option to compile through real LaTeX (XeLaTeX) instead of Typst, backed by a separate always-on compile container that keeps per-document compile state warm until it is manually turned off. This mirrors Overleaf's CLSI design: persistent per-project compile directories inside a long-lived sandboxed compiler, so recompiles never start from zero.

Phases: 1 and 2 ship page mode end to end (no open decisions, can start now). 3 to 7 ship LaTeX mode. Phase 3 can run in parallel with 1/2 (different files). Phase 4 depends only on the Phase 0 contract. 5 needs 3+4, 6 needs 5, 7 needs 4+5. Each phase is self-contained and executable in a fresh session.

Worktree note (from skill-observations/log.md obs 1): fresh worktrees share the main repo `.venv` via the absolute path in `.claude/launch.json`, but have no `frontend/node_modules`. Run `npm ci` in `<worktree>/frontend` first. SQLite DB is per-worktree at the worktree root. Commit with `git commit -F <file>` (PowerShell here-strings mangle messages), and never round-trip template/source files through PS pipelines (UTF-8 mojibake).

---

## Phase 0: Discovery + research findings (consolidated, verified 2026-07-30)

### How rendering actually works today (cited, do not re-derive)

- **The preview is already an Overleaf-style server recompile loop.** There is no client WASM. `frontend/src/pages/Studio/Preview.tsx:107-118` renders `svgs: string[]` (one `<div class="sheet">` per page, `dangerouslySetInnerHTML`), fed by server compiles. `.sheet svg { width: 100%; height: auto }` at `frontend/src/styles.css:211-215` means a single tall SVG page renders correctly with zero frontend changes.
- **Documents are self-contained Typst sources.** `backend/app/typstsvc/renderer.py:91-107` `render_source()` embeds `#let settings = (...)` and `#let data = (...)` as Typst dict literals and calls `#render(data, settings, photo: photo)`. Templates read settings with `.at(key, default:)` and **silently ignore unknown keys** (`templates/typst/common.typ:88-89`), so a new settings key needs zero plumbing to reach templates and stays backward-compatible with old stored sources.
- **Compiles run jailed and throwaway**: `templates/.compile/<uuid>/` with `--root templates/` and `--font-path templates/typst/fonts`, `shutil.rmtree` in `finally` (`renderer.py:156-189`). 30 s subprocess timeout (`renderer.py:132-147`), semaphore `compile_concurrency = 4` (`renderer.py:35-42`, `backend/app/config.py:54`).
- **The one-page fitting loop is the thing continuous mode must bypass.** `renderer.py:233-307` `compile_document()`: overflow tightens density, underflow grows `font_scale` toward `_FILL_TARGET = 0.95`. Gate: `if kind == "cv" and fit_one_page and result.ok:` at `renderer.py:264`. **`fit_one_page: bool = True` already exists as a parameter (`renderer.py:240`) and no caller passes it** (`backend/app/jobs.py:199-204`, `backend/app/routers/documents.py:102-104` and `:186-188` all omit it). That is the seam.
- `measure_fill` (`renderer.py:192-230`) divides the `<cvg-end>` anchor y by `_PAGE_H_PT = 841.89` (A4, `renderer.py:30`). Meaningless under auto height; never called when the fit gate is off, so no change needed there.
- **Page setup sites, all four, all hardcode A4** (statements inside `#let render(...) = {`, no leading `#`):
  - `templates/typst/cv_onyx.typ:50` `set page(paper: "a4", margin: (x: p.margin-x, top: p.margin-y, bottom: p.margin-y))`
  - `templates/typst/cv_classic.typ:29` (same, `x: p.margin-x + 0.25cm`)
  - `templates/typst/cv_compact.typ:25` (same, reduced margins)
  - `templates/typst/letter.typ:15` (fixed cm margins)
- **Settings storage is a JSON blob**, `backend/app/models.py:102` (`Document.settings`), schema `backend/app/schemas.py:120-126` (`DocSettings`: `template, accent, density, show_photo, font_scale, lang`), TS mirror `frontend/src/api.ts:34-36` (hand-mirrored, no codegen). `PUT /api/documents/{id}` writes it at `documents.py:95-98`, recompiles, and returns fresh `svgs` in the same response. The renderer's settled density/scale is written back at `documents.py:108-112` via dict spread, which preserves unknown keys.
- **No Alembic.** Migration path is `_ensure_columns` in `backend/app/db.py:41-48` (ALTER TABLE at startup; `jobs.gen_params` is the only precedent) plus `create_all` for new tables. Adding keys inside the `settings` JSON needs no migration at all.
- **Settings UI does not exist yet.** `useDocument.ts:93-99` `updateSettings` is exposed and never called by any component. The card-list option pattern to copy is the intensity picker at `frontend/src/pages/Studio/NewJobPanel.tsx:288-306` (cards, not segments; the de-overflow lesson from commit `e54aa06`).
- **Downloads** are plain anchors in the Preview toolbar (`Preview.tsx:90-104`): `.typ` at `/api/documents/{id}/source.typ` and PDF at `/api/documents/{id}/pdf`. Filenames are server-side `Content-Disposition` (`documents.py:238-243`, `:259`). A `.tex` twin is symmetric. PDF is lazily compiled and cached on the row (`documents.py:230-237`), invalidated by `doc.pdf = None` (`:117`, `:145`).
- **Compile endpoints** (`backend/app/routers/documents.py`): GET doc `:60-73` (compiles `doc.source`), PUT `:76-119` (data mode `compile_document` at `:102`, source mode `compile_source` at `:114`), POST `/{id}/compile` `:122-155` (source mode, `_MAX_SOURCE = 200_000` at `:19`, import jail regex at `:137-138`), chat `:158-218` (compile at `:186`/`:194`, one repair round `:198`), PDF `:221-244`, source download `:247-260`.
- **Diagnostics UX today**: single `diagnostics: string` on the controller (`useDocument.ts:31`), rendered only inside the Source tab (`SourceEditor.tsx:49-56`). The Preview pane is silent on failure (stale SVGs stay up). `syncing` is a bare boolean (`useDocument.ts:30`, spinner at `Preview.tsx:88`).
- **Plans/tiers**: `backend/app/quota.py:11-32`. `PLANS`: guest/free/plus/pro; gating dimensions today are exactly `daily`, `parallel`, `templates` (frozen dataclass `Plan`). Template lock idiom: 403 `{"code": "template_locked"}` at `quota.py:66-70`. `User.plan` at `models.py:33`. **No quota check exists on any `/api/documents/*` endpoint**; compiles are unmetered today.
- **i18n**: flat dict `frontend/src/i18n.tsx`, `en` from `:5`, `fr` from `:116`, `de` from `:221`. Every new key goes in all three; `frontend/src/__tests__/i18n.test.ts:7-19` enforces exact key parity. `backend/tests/test_language.py` is about prompts/letter dates, not UI strings, and is untouched by these features.
- **Tests that pin current behavior**: `backend/tests/test_typst.py` asserts `pages == 1` at `:34, :45, :68` (and more); helpers `_cv_data()`/`_letter_data()` at `:20-25`; typst binary skip guard `:14-17`. The rhythm test `:168-191` regex-parses `common.typ` and requires exactly three density tuples in exact key order (do not add a fourth density or reorder keys). E2E flow `backend/tests/test_api.py:26-96` includes a settings PUT at `:67-70` and asserts on the embedded settings literal (`:99-117` asserts `'lang: "de"' in doc["source"]`); adding keys to the literal is safe, renaming existing ones is not. Gate env: `CVG_FAKE_AI=1` via `backend/tests/conftest.py`.
- **Ops**: `ops/deploy.py:42-75` declares the full runtime (service `cvglowup`, region `europe-west1`, project default `project-60fad876-6da7-41f3-bfd`, 512Mi/1cpu/conc 80/min 0/max 20, ENV_VARS + SECRETS). Build is implicit Cloud Build via `--source .` (`deploy_args` `:158-177`), so the root `Dockerfile` is the only image the current script can build. Pure decision functions `:82-233` are unit-tested by `ops/tests/test_deploy.py` (5 tests pin `deploy_args("cand-...")` single-positional, `:141-235`). Smoke uses `/api/healthz` because **Google's edge intercepts the literal path `/healthz` on `*.run.app`** (`ops/README.md:36-37`); any new service must avoid that path. Root `Dockerfile`: node build stage + `python:3.12-slim` + typst 0.14.2 static binary (~250 MB image); typst version is pinned in three places (`Dockerfile:18`, `.github/workflows/ci.yml:22`, `deploy.yml:33`). **No docker-compose exists anywhere; local dev is native** (backend `python -m backend.scripts.serve` on 8011, vite on 5173). Docker Desktop 28 + compose v2.33 are installed on this machine.
- **Config**: pydantic-settings `backend/app/config.py` (field name == UPPERCASE env var, `.env` at repo root), feature flags as computed properties (`ai_enabled :116-118`, `billing_enabled :120-122`). `/api/config` exposes capability flags to the frontend (`backend/app/routers/account.py:22-25`). Admin scripts target prod by fetching `DATABASE_URL` from Secret Manager and setting the env var before importing config (`backend/scripts/grant_plan.py:37-54, :92-94`).
- **The docgen bench** (`backend/evals/docgen_compare/`, run-20260721): typst 187 ms warm median vs quarto 1590 ms vs **tectonic (XeTeX) 2992 ms warm, 65 s cold on an empty package cache**. Its verdict ("do not swap the engine", README.md:110-122) was about AI-authored source, not a deterministic-template LaTeX path, and it is the reason the LaTeX feature must ship as an opt-in on a warm service rather than as an engine swap. `references/ref.tex` is the only tracked `.tex` in the repo; the legacy `CV.tex`/`CoverLetter.tex` exist only in git history (`eb1c41b`, `54552ed`).

### External research (sources)

- **Typst `height: auto`**: the page grows to fit content; automatic page breaks do not occur (only explicit ones); margins still apply; an explicit `height` overrides the `paper` shorthand. Exactly the "infinite one page" semantics. Source: https://typst.app/docs/reference/layout/page/ . The repo's own skill already records this as the continuous-page mechanism (`.claude/skills/typst-doc-engine/SKILL.md:38`).
- **Overleaf CLSI architecture** (the model for the warm service): REST endpoint `POST /project/<id>/compile` with a file list; "the files and LaTeX environment will be persisted between requests" keyed by project id; compiles run latexmk in sandboxed sibling Docker containers from a TeX Live image (`SANDBOXED_COMPILES`, `TEXLIVE_IMAGE`, `PROCESS_LIFE_SPAN_LIMIT_MS`); resources cached by modified date. Source: https://github.com/overleaf/overleaf/blob/main/services/clsi/README.md . Our translation: one long-lived Cloud Run instance (or one local Docker container) is the sandbox; per-document compile dirs inside it are the persisted "LaTeX environment"; latexmk's `.fdb_latexmk`/aux reuse plus a baked font cache is what "not from zero" buys.
- **Cloud Run warm-instance economics**: active vCPU $0.0864/h; idle min-instance vCPU $0.0000025/vCPU-s. A 1 vCPU + 2 GiB service pinned to min-instances=1 idles at roughly $7-9/month, and $0 when scaled to zero. Session affinity exists (cookie, best effort) for routing repeat compiles to the same instance. Sources: https://cloud.google.com/run/pricing , https://cloudchipr.com/blog/cloud-run-pricing , https://docs.cloud.google.com/run/docs/configuring/session-affinity .
- **TeX distribution for the image**: Debian TeX Live subsets give a basic-scheme footprint well under 1 GB uncompressed (reference points: basic-scheme devcontainer 467 MB, full 4.2 GB). Tectonic stays the bench's engine for AI-authored source, but it fetches packages over the network on first use (65 s cold in our own bench), which is wrong for a deterministic service. Sources: https://hub.docker.com/r/texlive/texlive , https://formatex.io/blog/why-texlive-docker-images-are-4gb .
- **Client-side LaTeX (rejected for now)**: SwiftLaTeX compiles XeTeX/pdfTeX to WASM (~2x native speed) but has ICU/linebreaking gaps and a mostly dormant upstream; not a fit while the server loop already exists. Source: https://github.com/SwiftLaTeX/SwiftLaTeX .
- **PDF page-size ceiling**: PDF readers conventionally cap a page at 200 x 200 inches (14400 pt). A continuous CV hits 14400 pt at roughly 17 stacked A4 pages of content; treat that as a soft warning threshold, not a plausible user path.

### Contract locked for all phases

**Two new `DocSettings` keys** (house idiom: plain `str` + comment + runtime whitelist; no `Literal`/`Enum` anywhere in `backend/app`):

- `page_mode: str = "paged"  # paged | continuous`
- `compiler: str = "typst"  # typst | latex`

**Coercion rules** (enforced in `documents.py` on every settings write, silent fallback like the language whitelist idiom):

1. Unknown `page_mode` -> `"paged"`; unknown `compiler` -> `"typst"`.
2. `compiler == "latex"` requires: `kind == "cv"`, `template == "onyx"`, plan with `latex=True` (403 `latex_locked` if the plan check fails; silent coercion for kind/template).
3. `compiler == "latex"` forces `page_mode = "paged"` and `show_photo = False` (v1; continuous is Typst-only, photo needs tikz-class machinery LaTeX v1 does not take on).
4. Letters support `page_mode` (both values). `message` kind has no settings UI (unchanged).

**latexc wire contract v1** (single source of truth `services/latexc/contract.py`, imported by the backend as `services.latexc.contract` and copied into the latexc image; both images carry the same file):

- `POST /v1/compile` body `LatexCompileIn { doc_id, engine: "xelatex", main: "main.tex", files: [{path, content_b64}], want_svgs: true, timeout_s: 40 }` -> `LatexCompileOut { ok, cache: "hit"|"warm"|"cold", pages, pdf_b64, svgs: [str], log_tail, error_line, timings_ms: {sync, compile, convert, total} }`
- `DELETE /v1/project/{doc_id}` clears that document's compile dir. `GET /v1/status` returns `{ ok, uptime_s, projects, disk_mb }` (never route anything at `/healthz`).
- Auth: `Authorization: Bearer <LATEXC_TOKEN>` on every route, constant-time compare.
- File rules: flat names matching `^[A-Za-z0-9._-]{1,64}$` (no slashes), max 16 files, 4 MB total, content base64.

**Warmth semantics** (the "stays active until manually turned off" ask):

- Local: the latexc Docker container runs via compose and stays up until `docker compose down`. Warm by construction.
- Prod: enabling LaTeX on a document calls `POST /api/latex/warmup`, which sets the latexc Cloud Run service to `min-instances=1` via the Admin API if it is not already warm. It then **stays warm until manually turned off** with `python ops/latexc.py off` (or the safety reaper, decision 2 below). "End session" in the studio clears that document's remote compile dir only; it never scales the service down on its own.
- Per-document cache: latexc keeps `/tmp/compiles/<doc_id>/` between requests (aux files, `.fdb_latexmk`, last PDF), LRU-evicted beyond 40 projects or 512 MB. A content hash short-circuits unchanged recompiles to `cache: "hit"` with the stored outputs.
- Boot prewarm: latexc compiles an embedded probe CV on startup so the first user compile after any deploy or scale-up is already warm (fontconfig cache is baked at image build).

**Preview parity**: latexc converts its PDF to per-page SVGs server-side (`pdftocairo -svg`, one page per file), so the studio preview consumes the identical `svgs: string[]` shape and `Preview.tsx` needs no rendering changes. SVG text arrives as glyph outlines, same as Typst SVGs (the existing "never assert on strings inside SVGs" rule holds).

**AI boundary**: the LLM never writes LaTeX (same contract as Typst, `typst-doc-engine` skill). In latex mode: chat editing works in data mode (edits JSON, deterministic re-render); chat is disabled when the user hand-edits `.tex` source (no AI repair round on raw LaTeX).

### Anti-pattern guards (global)

- No pydantic `Literal`/`Enum`; str + comment + whitelist only.
- Option pickers are card lists, never segmented controls (de strings overflow, commit `e54aa06`).
- Every i18n key lands in `en`, `fr`, and `de` in the same commit; the vitest parity gate fails otherwise.
- Do not add a fourth density tuple or reorder density keys in `common.typ` (rhythm test regex, `test_typst.py:168-191`).
- Do not touch `_FILL_MIN`/`_FILL_TARGET`/`_PAGE_H_PT`; continuous mode bypasses the fit loop, it does not re-tune it.
- No new heavyweight frontend deps (no pdf.js, no react-pdf); the SVG pipeline already covers preview.
- Never route a health endpoint at `/healthz` (Google edge intercepts it on `*.run.app`); use `/v1/status` on latexc and keep `/api/healthz` on the app.
- Config is code: latexc runtime settings live in `ops/latexc.py` the same way the app's live in `ops/deploy.py`; no manual `gcloud run services update` (wiped on next deploy).
- `services/latexc` must not import from `backend.*`, and `backend.*` imports only `services.latexc.contract` (contract boundary; the two deploy independently).
- LaTeX escaping is a single-pass simultaneous regex; never chain sequential `str.replace` (double-escapes backslashes).
- Windows/PS: use Edit/Write tools on sources, `git commit -F`, remember port 8000 is taken (backend 8011, vite 5173, latexc local 8021).

### Decision points (recommendations first; phases 1-2 are unblocked either way)

1. **Which plans get LaTeX?** Recommended: `plus` and `pro` (`latex=True` on both). It is a paid differentiator with real compute cost; free/guest keep Typst. Alternative: pro-only.
2. **Idle safety reaper.** The ask is "active until manually turned off". Recommended deviation: a backend reaper scales latexc to zero after 240 min without any LaTeX compile, `LATEXC_IDLE_OFF_MINUTES=240`, settable to `0` to disable and honor the ask literally. Reason: a forgotten warm instance costs ~$8/month and this account was suspended once over EUR 3.71 past due. The manual `ops/latexc.py off` path exists regardless.
3. **v1 scope.** Recommended: page mode covers CV + letter; LaTeX covers CV on the onyx template only (classic/compact ports and letters follow as data, not new architecture). Photo unsupported in LaTeX v1.
4. **TeX distribution.** Recommended: Debian TeX Live subset (`texlive-xetex` + recommended sets + `latexmk`), fully offline, deterministic, latexmk incremental aux reuse; image ~1 GB. Alternative: tectonic with a baked package cache (~200 MB image) but XeTeX-only via a niche toolchain and a history of runtime network fetches.
5. **Deploy integration.** Recommended: a self-contained `ops/latexc.py` that imports `ops/deploy.py`'s pure helpers and implements the same candidate -> smoke -> promote shape for the latexc service, leaving `ops/deploy.py` and its 5 pinned tests untouched. Alternative: refactor deploy.py around a ServiceSpec dataclass (cleaner long-term, more churn now).

---

## Phase 1: page mode, backend + templates

### What to implement

1. `backend/app/schemas.py` (`DocSettings`, `:120-126`): add `page_mode: str = "paged"  # paged | continuous` after `font_scale`. Copy the comment idiom from `density`.

2. `backend/app/routers/documents.py:95-98`, extend the settings write with the whitelist:

```python
    if body.settings is not None:
        new_settings = body.settings.model_dump()
        if new_settings.get("page_mode") not in ("paged", "continuous"):
            new_settings["page_mode"] = "paged"
        doc.template_id = new_settings.get("template", doc.template_id)
        doc.settings = new_settings
```

3. Thread the fit flag at the three `compile_document` call sites, deriving it from the settings dict actually being compiled:

- `documents.py:102-104` (PUT, data mode):

```python
        result, source = await compile_document(
            doc.kind, doc.template_id, doc.data, doc.settings, photo=photo,
            fit_one_page=(doc.settings or {}).get("page_mode") != "continuous",
        )
```

- `documents.py:186-188` (chat): same `fit_one_page=` line, same expression.
- `backend/app/jobs.py:199-204`: same keyword. Fresh generations default to `"paged"` via the schema, so behavior is unchanged; the keyword is passed anyway so the seam is explicit.

4. Parameterize page height in all four templates. Pattern for `templates/typst/cv_onyx.typ:50` (statement form, inside `render`):

```typst
  let continuous = settings.at("page_mode", default: "paged") == "continuous"
  set page(
    width: 21cm,
    height: if continuous { auto } else { 29.7cm },
    margin: (x: p.margin-x, top: p.margin-y, bottom: p.margin-y),
  )
```

Apply the same two-line change to `cv_classic.typ:29`, `cv_compact.typ:25`, and `letter.typ:15`, keeping each file's existing margin expression byte-identical. `width: 21cm, height: 29.7cm` is exactly `paper: "a4"`; the explicit form exists because `height` must be conditional (an explicit height overrides the paper shorthand, per the Typst page docs).

5. `backend/app/typstsvc/renderer.py`: no logic changes. Add one line to the module docstring under the fitting note: `Continuous page mode (settings.page_mode == "continuous") is compiled with fit_one_page=False by all callers; the fit loop and measure_fill are A4-only by design.`

### Tests (backend/tests/test_typst.py, mirror existing style)

```python
@pytest.mark.parametrize("template", ["onyx", "classic", "compact"])
async def test_continuous_mode_renders_one_tall_page(template):
    data = _cv_data()
    data["experience"] = data["experience"] * 4  # would overflow A4
    settings = {"template": template, "accent": "#C2551B", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en",
                "page_mode": "continuous"}
    result, source = await renderer.compile_document(
        "cv", template, data, settings, fmt="svg", fit_one_page=False)
    assert result.ok, result.diagnostics
    assert result.pages == 1
    m = re.search(r'height="([0-9.]+)pt"', result.svgs[0])
    assert m and float(m.group(1)) > 841.89, "page did not grow past A4"
    assert result.density_used == "normal", "fit loop ran despite continuous mode"


async def test_continuous_letter_compiles():
    settings = {"template": "classic", "accent": "#1C3B5A", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en",
                "page_mode": "continuous"}
    result, _ = await renderer.compile_document(
        "letter", "classic", _letter_data(), settings, fmt="svg", fit_one_page=False)
    assert result.ok, result.diagnostics
    assert result.pages == 1


async def test_paged_default_still_fits_one_page():
    # page_mode absent entirely (old stored settings) must behave exactly as today
    data = _cv_data()
    data["experience"] = data["experience"] * 4
    settings = {"template": "onyx", "accent": "#0F62FE", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en"}
    result, _ = await renderer.compile_document("cv", "onyx", data, settings, fmt="svg")
    assert result.ok and result.pages == 1
    assert result.density_used in ("tight", "xtight")
```

Add `import re` to the test module imports. API-level test in `backend/tests/test_api.py` (after the existing settings PUT idiom at `:67-70`): PUT `settings={..., "page_mode": "continuous"}` on a generated CV, assert `resp["svgs"]` has length 1 and `'page_mode: "continuous"' in resp["source"]`; then PUT `page_mode="sideways"` and assert the stored document comes back `"paged"` (whitelist).

### Validation

```bash
cd backend && python -m pytest tests/test_typst.py tests/test_api.py -q && python -m ruff check backend
```

Expected: all pass, including the untouched `pages == 1` goldens (default is paged). PDF export needs no separate handling: `compile_document(fmt="pdf")` recompiles the settled source, and a continuous source yields a single tall PDF page.

Commit: `feat(pagemode): continuous single-page rendering behind DocSettings.page_mode`

---

## Phase 2: page mode, studio UI

### What to implement

1. `frontend/src/api.ts:34-36` (`DocSettings`): add `page_mode: string;`.

2. New `frontend/src/pages/Studio/SettingsPopover.tsx`, the first consumer of `ctl.updateSettings` (`useDocument.ts:93-99`). Gear button + popover in the Preview toolbar; card list copied from the intensity picker pattern (`NewJobPanel.tsx:288-306`):

```tsx
import { useState } from "react";
import { Settings2 } from "lucide-react";
import { useI18n } from "../../i18n";
import type { DocController } from "./useDocument";

const MODES = ["paged", "continuous"] as const;

export default function SettingsPopover({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const doc = ctl.doc;
  if (!doc || doc.kind === "message") return null;
  const settings = doc.settings;
  const sourceLocked = doc.mode === "source";

  const pick = (page_mode: string) => {
    if (sourceLocked || page_mode === settings.page_mode) return;
    void ctl.updateSettings({ ...settings, page_mode });
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="rounded-md p-1.5 text-text/60 transition-colors hover:text-text"
        aria-label={t("studio.settings.title")}
      >
        <Settings2 size={15} />
      </button>
      {open && (
        <div className="glass-panel absolute right-0 top-full z-20 mt-2 w-64 rounded-lg border border-black/10 p-3 shadow-lg">
          <p className="eyebrow mb-3">{t("studio.pagemode.title")}</p>
          <div className="space-y-2">
            {MODES.map((m) => (
              <button
                key={m}
                onClick={() => pick(m)}
                disabled={sourceLocked}
                className={`block w-full rounded-lg border px-3.5 py-2.5 text-left transition-colors ${
                  (settings.page_mode ?? "paged") === m
                    ? "border-flame-500 bg-flame-950"
                    : "border-black/10 glass-panel hover:border-ink-600"
                } ${sourceLocked ? "opacity-50" : ""}`}
              >
                <span className="block text-[13px] font-medium">{t(`studio.pagemode.${m}`)}</span>
                <span className="block text-[11px] text-text/50">{t(`studio.pagemode.${m}.desc`)}</span>
              </button>
            ))}
          </div>
          {sourceLocked && (
            <p className="mt-2 text-[11px] text-text/50">{t("studio.settings.sourcelock")}</p>
          )}
        </div>
      )}
    </div>
  );
}
```

Notes: `updateSettings` is not debounced and returns fresh `svgs` in the same PUT response (`useDocument.ts:54-70`), so the preview updates on click with no extra wiring. In source mode a settings PUT would not regenerate the source (`documents.py:114` recompiles `doc.source` untouched), hence the disable + hint instead of a silent no-op.

3. Mount it in the Preview toolbar, `Preview.tsx:90-104` region, next to the zoom controls: `<SettingsPopover ctl={ctl} />`. Export the `DocController` type from `useDocument.ts` if not already exported.

4. i18n keys, all three blocks of `frontend/src/i18n.tsx` (en `:5`, fr `:116`, de `:221`):

| key | en | fr | de |
|---|---|---|---|
| `studio.settings.title` | Layout | Mise en page | Layout |
| `studio.pagemode.title` | Page layout | Format de page | Seitenlayout |
| `studio.pagemode.paged` | A4 pages | Pages A4 | A4-Seiten |
| `studio.pagemode.paged.desc` | Print-ready pages with breaks | Pages classiques, prêtes à imprimer | Klassische Seiten, druckfertig |
| `studio.pagemode.continuous` | Continuous | Continu | Fortlaufend |
| `studio.pagemode.continuous.desc` | One endless page, no breaks. Best shared digitally. | Une seule page sans coupure. Idéal en ligne. | Eine endlose Seite ohne Umbrüche. Ideal digital. |
| `studio.settings.sourcelock` | Locked while editing source. Revert to change layout. | Verrouillé en mode source. Revenez au mode guidé. | Im Quellmodus gesperrt. Zum Ändern zurücksetzen. |

5. No preview-loop changes: a continuous doc returns one SVG; `.sheet` renders it at full width and natural height. The A4 placeholder (`Preview.tsx:114`) only shows before the first render; leave it.

### Tests + validation

```bash
cd frontend && npm test && npm run build
```

(vitest parity gate covers the new keys; tsc covers the `DocSettings` change.) Browser verification via the preview tools (`cvglowup` launch config, port 8011 + vite): generate a CV with the fake AI (`CVG_FAKE_AI=1`), open the popover, switch to Continuous, confirm the preview collapses to a single tall sheet and the downloaded PDF is one tall page; switch back; enter source mode and confirm the cards are disabled with the hint. Screenshot as proof.

Commit: `feat(pagemode): studio layout popover (first updateSettings consumer) + i18n`

---

## Phase 3: LaTeX document renderer (backend, no service yet)

Deterministic CVData -> `.tex`, mirroring the Typst path's "LLM never writes markup" contract. Pure Python, no new deps, no TeX needed to run gate tests.

### What to implement

1. New package `backend/app/texsvc/__init__.py` (empty) + `backend/app/texsvc/escape.py`:

```python
"""LaTeX escaping. Single simultaneous-pass regex: sequential str.replace would
double-escape the backslash expansion. Mirrors the typst_literal contract:
user strings are data, never markup."""
import re
import unicodedata

_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}
_RE = re.compile("|".join(re.escape(k) for k in _SPECIALS))


def esc(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    s = "".join(ch for ch in s if ch == "\n" or ord(ch) >= 32)
    s = s.replace("\u2028", "\n").replace("\u2029", "\n")
    return _RE.sub(lambda m: _SPECIALS[m.group(0)], s)
```

2. `backend/app/texsvc/tex_onyx.py`: `render_tex(data: dict, settings: dict) -> str` producing a complete standalone `main.tex`. Layout ports `templates/typst/cv_onyx.typ` (visual reference; open it side by side while porting). Structure:

- Preamble: `\documentclass[10pt]{article}`, `geometry` with the density margins copied from `common.typ:90-117` (normal: `1.1cm`/`1.15cm`; tight: `0.95cm`/`1.05cm`; xtight: `0.85cm`/`0.95cm`), `fontspec` with `\setmainfont{IBM Plex Sans}` (fonts are installed system-wide in the latexc image from `templates/typst/fonts/`), `xcolor` with `\definecolor{accent}{HTML}{...}` parsed from `settings["accent"]` (strip `#`, validate `^[0-9a-fA-F]{6}$`, fallback `C2551B`), `hyperref` (`hidelinks`), `\pagestyle{empty}`.
- Font scale: multiply the base/small/name/heading pt sizes from the density tuple by `settings["font_scale"]` clamped to `[0.8, 1.5]`, emitted via `\fontsize{..}{..}\selectfont` helpers, mirroring `common.typ:118-129` (`gap-scale = max(scale, 1.0)` for the fixed gaps).
- Body: name + headline header, contact row, then the same section order the Typst template renders; entries as bold role + accent-colored company line + date column (`\hfill`), bullets as plain `itemize` with `\setlength` spacing from the density tuple (no `enumitem`, keeps the package set small).
- Every user string passes through `esc()`. Section labels reuse the language table already ported for Typst (`common.typ:78` semantics): duplicate the 3-language label dict as a Python dict here with a comment pointing at `common.typ`.
- `lastpage`/page numbers: none (`\pagestyle{empty}`), the CV is one or more clean pages.

3. Fixture: `backend/tests/fixtures/expected_onyx.tex` is NOT created (no brittle snapshot). Tests assert structure and escaping instead.

### Tests (backend/tests/test_texsvc.py, gate lane, no TeX binary)

```python
import re

from backend.app.texsvc.escape import esc
from backend.app.texsvc.tex_onyx import render_tex

from .test_typst import _cv_data  # reuse the fixture loader


def test_escape_adversarial():
    s = esc("100% & more_ #1 {x} \\ ~^ $5")
    for frag in (r"\%", r"\&", r"\_", r"\#", r"\{", r"\}",
                 r"\textbackslash{}", r"\textasciitilde{}", r"\textasciicircum{}", r"\$"):
        assert frag in s
    assert "\x00" not in esc("a\x00b")


def test_escape_no_double_escape():
    assert esc("\\&") == r"\textbackslash{}\&"


def test_render_tex_structure_and_no_raw_specials():
    settings = {"template": "onyx", "accent": "#C2551B", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "de",
                "page_mode": "paged", "compiler": "latex"}
    tex = render_tex(_cv_data(), settings)
    assert tex.startswith("\\documentclass")
    assert "\\definecolor{accent}{HTML}{C2551B}" in tex
    assert "IBM Plex Sans" in tex
    body = tex.split("\\begin{document}", 1)[1]
    # no unescaped specials may survive in body text (commands all start with \)
    assert not re.search(r"(?<!\\)[&#_]", re.sub(r"\\[A-Za-z]+", "", body).replace(r"\&", "").replace(r"\_", "").replace(r"\#", ""))


def test_render_tex_bad_accent_falls_back():
    settings = {"template": "onyx", "accent": "#zzzzzz", "density": "normal",
                "show_photo": False, "font_scale": 1.0, "lang": "en",
                "page_mode": "paged", "compiler": "latex"}
    assert "\\definecolor{accent}{HTML}{C2551B}" in render_tex(_cv_data(), settings)
```

(If importing from `test_typst` trips the module-level typst skip guard, move `_cv_data` into a tiny `backend/tests/fixtures_util.py` and import it from both files; keep the diff minimal.)

### Validation

```bash
cd backend && python -m pytest tests/test_texsvc.py -q && python -m ruff check backend
```

Real compile proof arrives in Phase 4's container tests (this phase has no TeX). Commit: `feat(latex): deterministic CVData -> .tex renderer (onyx port) with escaping tests`

---

## Phase 4: services/latexc, the warm compile service

New top-level `services/` tree (first service split per the services-first rule; self-contained: own code, tests, Dockerfile, README, compose).

### Files

```
services/__init__.py                 (empty)
services/latexc/__init__.py          (empty)
services/latexc/contract.py          wire models, CONTRACT_VERSION = "1"
services/latexc/app.py               FastAPI app, auth, routes
services/latexc/runner.py            latexmk + pdftocairo subprocess logic
services/latexc/cache.py             per-doc dirs, hashing, LRU eviction
services/latexc/probe.tex            tiny valid CV used for boot prewarm + tests
services/latexc/requirements.txt     fastapi, uvicorn, pydantic, httpx, pytest, pytest-asyncio (pin to backend/requirements*.txt versions; test deps ride along because the suite runs inside the container)
services/latexc/Dockerfile
services/latexc/compose.yml
services/latexc/cloudbuild.yaml
services/latexc/README.md            contract, run, test, deploy, off-switch
services/latexc/tests/__init__.py
services/latexc/tests/test_compile.py
services/latexc/tests/test_security.py
services/latexc/tests/test_cache.py
```

### What to implement

1. `contract.py` (verbatim, the one file both sides share):

```python
"""latexc wire contract v1. Imported by backend (services.latexc.contract) and
by the service itself. Bump CONTRACT_VERSION on breaking changes and update
both deploys together."""
from pydantic import BaseModel, Field

CONTRACT_VERSION = "1"
FILE_NAME_RE = r"^[A-Za-z0-9._-]{1,64}$"
MAX_FILES = 16
MAX_TOTAL_BYTES = 4_000_000


class CompileFile(BaseModel):
    path: str = Field(pattern=FILE_NAME_RE)
    content_b64: str


class LatexCompileIn(BaseModel):
    doc_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    engine: str = "xelatex"  # xelatex (only value in v1)
    main: str = Field(default="main.tex", pattern=FILE_NAME_RE)
    files: list[CompileFile]
    want_svgs: bool = True
    timeout_s: int = Field(default=40, ge=5, le=60)


class LatexCompileOut(BaseModel):
    ok: bool
    cache: str = "cold"  # hit | warm | cold
    pages: int = 0
    pdf_b64: str | None = None
    svgs: list[str] = []
    log_tail: str = ""
    error_line: str | None = None
    timings_ms: dict[str, int] = {}


class LatexStatus(BaseModel):
    ok: bool = True
    version: str = CONTRACT_VERSION
    uptime_s: int
    projects: int
    disk_mb: float
```

2. `runner.py` core (async, same shape as `renderer._run_typst`):

- `sync_files(project_dir, files)`: decode b64, reject if joined size > `MAX_TOTAL_BYTES`, write flat (pydantic already enforced the name pattern; assert `"/" not in path` and `".." not in path` anyway, defense in depth).
- `compile(project_dir, main, timeout_s)`: run

```python
cmd = ["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
       "-file-line-error", "-no-shell-escape", main]
env = {**os.environ, "TEXMFVAR": str(project_dir / ".texmf-var"),
       "TEXMFCONFIG": str(project_dir / ".texmf-cfg"),
       "openout_any": "p", "openin_any": "p", "HOME": str(project_dir)}
```

with `cwd=project_dir`, `asyncio.wait_for(..., timeout=timeout_s)`, kill on timeout. Keep aux files (that is the warm cache); only `DELETE /v1/project/{id}` or LRU eviction removes the dir.
- `error_line(log)`: first match of `re.search(r"^(?:! |.*?:\d+: )(.+)$", log, re.M)`, else None. `log_tail`: last 20_000 chars of `main.log` (fallback: process stderr).
- `to_svgs(project_dir, pdf_path)`: `pdfinfo` for the page count, then per page `pdftocairo -svg -f {n} -l {n} main.pdf page-{n}.svg`; read strings in order. `pages` = that count (also returned when `want_svgs` is false, via `pdfinfo` alone).

3. `cache.py`: `project_dir(doc_id) = COMPILE_ROOT/<doc_id>`; `content_key = sha256(engine + main + sorted((f.path, f.content_b64)))`; store `last.json {content_key, pages}` + `last.pdf` + `page-*.svg` beside the aux files. On request: same key and outputs present -> `cache="hit"`, return stored outputs without running TeX. Dir existed but key differs -> `cache="warm"` (aux reuse). Fresh dir -> `cache="cold"`. Eviction: after each compile, if project count > 40 or `du` > 512 MB, delete oldest-mtime dirs first (never the one just used). One `asyncio.Lock` per doc_id (dict of locks) so concurrent compiles of the same doc serialize; global `asyncio.Semaphore(2)` caps TeX processes.

4. `app.py`: FastAPI, no docs endpoints, routes from the contract. Auth dependency: `hmac.compare_digest(bearer_token, os.environ["LATEXC_TOKEN"])`, 401 otherwise; refuse to boot if `LATEXC_TOKEN` is unset. Startup event: copy `probe.tex` into `COMPILE_ROOT/_probe/` and compile it once (log timing; failures log loudly but do not crash the service). `GET /v1/status` fills `LatexStatus` (uptime from a module start timestamp, project count and disk from `COMPILE_ROOT`).

5. `Dockerfile` (build context = repo root, so it can COPY the fonts):

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-xetex texlive-latex-recommended texlive-fonts-recommended \
    latexmk poppler-utils fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Same font files the Typst preview uses -> identical glyphs in both compilers.
COPY templates/typst/fonts /usr/local/share/fonts/cvglowup
RUN fc-cache -f

WORKDIR /srv
COPY services/latexc/requirements.txt latexc/requirements.txt
RUN pip install --no-cache-dir -r latexc/requirements.txt
COPY services/latexc/ latexc/

RUN useradd --create-home texuser && mkdir -p /tmp/compiles && chown -R texuser /tmp/compiles
USER texuser
ENV PORT=8080 COMPILE_ROOT=/tmp/compiles PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["sh", "-c", "uvicorn latexc.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

Note: on Cloud Run `/tmp` is in-memory; the 512 MB cache cap plus 2 GiB instance memory is the budget. Record the measured image size in the README after the first build (estimate: 900 MB to 1.3 GB; acceptable, image streaming plus min-instances hides it).

6. `compose.yml` (local dev; container persists until `docker compose down`, which is the local off-switch):

```yaml
services:
  latexc:
    build:
      context: ../..
      dockerfile: services/latexc/Dockerfile
    ports:
      - "8021:8080"
    environment:
      LATEXC_TOKEN: dev-token
```

7. `cloudbuild.yaml` (repo-root context so the fonts COPY works):

```yaml
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build", "-f", "services/latexc/Dockerfile",
           "-t", "${_IMAGE}", "."]
images: ["${_IMAGE}"]
```

8. Tests (run inside the container; they exercise real TeX):

- `test_compile.py`: compile `probe.tex` via the HTTP app (`httpx.ASGITransport`), assert `ok`, `pages == 1`, `pdf_b64` decodes to `%PDF`, `svgs[0].startswith("<svg")`; second identical request returns `cache == "hit"` with no new compile timestamp; a one-character content change returns `cache == "warm"` and a fresh PDF.
- `test_security.py`: missing/wrong bearer -> 401; `path: "../evil.tex"` and `path: "a/b.tex"` -> 422 (pydantic pattern); a source containing `\write18{id}` compiles with shell-escape refused (assert no `write18` output file and log contains the disabled notice, or compile fails cleanly); `\input{/etc/passwd}` fails (openin_any=p) rather than leaking content into the PDF; a `\loop\repeat` infinite source gets killed at `timeout_s` and returns `ok=False` with `error_line`.
- `test_cache.py`: LRU eviction beyond the project cap; per-doc lock serializes two concurrent compiles of one doc.

### Validation

```bash
docker compose -f services/latexc/compose.yml up -d --build
docker compose -f services/latexc/compose.yml exec latexc python -m pytest /srv/latexc/tests -q
curl -s -H "Authorization: Bearer dev-token" http://localhost:8021/v1/status
```

Expected: tests pass inside the container, status returns `{"ok": true, ...}`. Record warm vs cold compile timings from `timings_ms` in the README (targets: warm < 2500 ms p95 for a 1-2 page CV, boot prewarm < 30 s). Add a CI job in `.github/workflows/ci.yml` (main-only, `needs: [backend]`, mirroring the existing `docker` job at `:59-66`): build the latexc image and run the container test suite.

Commit: `feat(latexc): warm sandboxed LaTeX compile service (CLSI-style per-doc cache) + container tests`

---

## Phase 5: backend integration

### What to implement

1. `backend/app/config.py` fields (env-mapped automatically): `latexc_url: str = ""`, `latexc_token: str = ""`, `latexc_idle_off_minutes: int = 240`, plus

```python
    @property
    def latex_enabled(self) -> bool:
        return bool(self.latexc_url and self.latexc_token)
```

Add all three to `.env.example` with comments.

2. `backend/app/quota.py`: add `latex: bool = False` to the frozen `Plan` dataclass (keyword default, existing positional constructions stay valid) and set `latex=True` on `plus` and `pro` (decision 1). Expose `"latex": plan.latex` in `quota_snapshot` (`:149-162`).

3. `backend/app/schemas.py` `DocSettings`: add `compiler: str = "typst"  # typst | latex`.

4. `documents.py` settings write grows the compiler rules (extends the Phase 1 block; `latex_locked` mirrors the `template_locked` idiom at `quota.py:66-70`):

```python
    if body.settings is not None:
        new_settings = body.settings.model_dump()
        if new_settings.get("page_mode") not in ("paged", "continuous"):
            new_settings["page_mode"] = "paged"
        if new_settings.get("compiler") not in ("typst", "latex"):
            new_settings["compiler"] = "typst"
        if new_settings["compiler"] == "latex":
            if not get_settings().latex_enabled or doc.kind != "cv" or new_settings.get("template") != "onyx":
                new_settings["compiler"] = "typst"
            elif not plan_for(user).latex:
                raise HTTPException(status_code=403, detail={
                    "code": "latex_locked",
                    "message": "The LaTeX compiler requires a higher plan."})
            else:
                new_settings["page_mode"] = "paged"
                new_settings["show_photo"] = False
        doc.template_id = new_settings.get("template", doc.template_id)
        doc.settings = new_settings
```

(`user` is already available in the PUT handler; guests get `plan_for(None) -> guest -> latex=False -> 403`.)

5. `backend/app/texsvc/client.py`: thin httpx client returning the Typst `CompileResult` shape so routers stay engine-agnostic:

```python
"""HTTP client for services/latexc. Returns typstsvc.renderer.CompileResult so
routers dispatch once and stay engine-agnostic."""
import base64

import httpx

from services.latexc.contract import CompileFile, LatexCompileIn, LatexCompileOut

from ..config import get_settings
from ..typstsvc.renderer import CompileResult

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = httpx.AsyncClient(
            base_url=s.latexc_url,
            headers={"Authorization": f"Bearer {s.latexc_token}"},
            timeout=50.0,
        )
    return _client


async def compile_tex(doc_id: str, tex_source: str) -> tuple[CompileResult, str]:
    body = LatexCompileIn(
        doc_id=doc_id,
        files=[CompileFile(path="main.tex",
                           content_b64=base64.b64encode(tex_source.encode()).decode())],
    )
    try:
        resp = await _http().post("/v1/compile", json=body.model_dump())
        resp.raise_for_status()
        out = LatexCompileOut.model_validate(resp.json())
    except httpx.HTTPError as e:
        return CompileResult(ok=False, diagnostics=f"LaTeX service unavailable: {e}"), tex_source
    if not out.ok:
        diag = (out.error_line or "LaTeX compile failed") + "\n\n" + out.log_tail[-4000:]
        return CompileResult(ok=False, diagnostics=diag), tex_source
    pdf = base64.b64decode(out.pdf_b64) if out.pdf_b64 else None
    return CompileResult(ok=True, pages=out.pages, pdf=pdf, svgs=out.svgs), tex_source
```

6. Engine dispatch in `documents.py`: one helper near `_get_doc`:

```python
def _is_latex(doc) -> bool:
    return (doc.settings or {}).get("compiler") == "latex"
```

- PUT data mode (`:102`): if `_is_latex(doc)`, build `source = render_tex(doc.data, doc.settings)` and `result, source = await compile_tex(doc.id, source)`; else the existing `compile_document(...)` call. Persist `doc.source = source` in both branches (source column now holds `.tex` when compiler is latex; update the comment at `models.py:104` to `# Typst or LaTeX source, per settings.compiler`).
- GET doc preview (`:70`): dispatch `compile_tex(doc.id, doc.source)` vs `compile_source(doc.source)`.
- POST `/{id}/compile` source mode (`:122-155`): when latex, skip the Typst-only import-jail regex (`:137-138`) and instead reject `\write18` up front (`re.search(r"\\write18", source)` -> 422 "shell escape is not allowed"); the sandbox is the real boundary. Same `_MAX_SOURCE` cap. Forward through `compile_tex`.
- Chat (`:158-218`): data mode dispatches like PUT. If `doc.mode == "source"` and `_is_latex(doc)`: return 409 `{"code": "chat_source_latex", "message": "Chat editing is unavailable while hand-editing LaTeX source."}` (the AI never writes LaTeX; there is no repair round).
- PDF (`:221-244`): when latex, `compile_tex` already returned `pdf` bytes alongside the svgs; cache to `doc.pdf` as today.

7. `.tex` download: mirror `download_source` (`:247-260`) at `GET /{doc_id}/source.tex`, 404 unless `_is_latex(doc)`; filename `{kind}-{id[:8]}.tex`.

8. Warmth control, new `backend/app/routers/latex.py` (`/api/latex`), registered in `main.py`:

- `POST /warmup` (auth required, plan must have `latex`): local/dev -> proxy `GET {latexc_url}/v1/status` and report `{warm: ok}`. Prod (`is_prod`) -> read the latexc service via the Cloud Run Admin API; if `minInstanceCount < 1`, PATCH it to 1. Return `{warm, starting}`.
- `GET /status` (auth required): `{enabled, warm, min_instances}` for the studio chip.
- `POST /session/{doc_id}/end` (auth, owner): `DELETE {latexc_url}/v1/project/{doc_id}`; returns 204. Never scales down.
- Admin API access: metadata-server token (`http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token`, header `Metadata-Flavor: Google`) + `PATCH https://run.googleapis.com/v2/projects/{p}/locations/{region}/services/cvglowup-latexc?updateMask=scaling.minInstanceCount` via httpx. Config additions: `latexc_service: str = "cvglowup-latexc"`, `latexc_region: str = "europe-west1"` (do not reuse `gcp_location`, which is the Vertex AI location at `config.py:38`).
- Idle reaper (decision 2): `asyncio` task started in the app lifespan next to the existing job machinery; every 10 min, if `latexc_idle_off_minutes > 0` and prod and warm and `now - last_latex_compile > threshold`, PATCH min-instances to 0. Last-compile tracking: new table

```python
class LatexActivity(Base):
    __tablename__ = "latex_activity"
    id: Mapped[int] = mapped_column(primary_key=True)  # single row, id=1
    last_compile_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

upserted after every successful `compile_tex` (new tables need no migration; `create_all` handles them, `db.py:51-57`).

9. `/api/config` (`account.py:22-25`): add `"latex_enabled": settings.latex_enabled`.

### Tests (gate lane, no TeX, monkeypatched client)

`backend/tests/test_latex_integration.py`:

- Fake `compile_tex` via monkeypatch returning a canned `CompileResult(ok=True, pages=1, svgs=["<svg ..."], pdf=b"%PDF-fake")`.
- Free user PUTs `compiler="latex"` -> 403 `latex_locked`. Plus user (upgrade via the `grant_plan.apply` path or direct row edit like `test_grant_plan.py`) -> 200, doc source now starts with `\documentclass`, response svgs served from the fake.
- `compiler="latex"` on a letter -> silently coerced back to `"typst"`. `page_mode` forced to `"paged"` when latex.
- `GET /{id}/source.tex` -> 200 with `Content-Disposition` filename; 404 on a typst doc.
- Chat on a latex source-mode doc -> 409 `chat_source_latex`.
- `latexc_url` unset -> `/api/config` has `latex_enabled: false` and PUT coerces compiler to typst.
- Contract import guard: `test_latexc_contract.py` asserts `services.latexc.contract.CONTRACT_VERSION == "1"` and that `LatexCompileIn` round-trips a sample payload (this is the cross-service parity gate; it runs with zero service code).

Root `Dockerfile`: add `COPY services/ services/` after the `COPY backend/` line (the backend image needs the contract module; a few KB). Neither ignore file excludes `services/`.

### Validation

```bash
cd backend && python -m pytest tests -q && python -m ruff check backend ops
```

Then end to end against the real container: `docker compose -f services/latexc/compose.yml up -d`, set `LATEXC_URL=http://localhost:8021` and `LATEXC_TOKEN=dev-token` in `.env`, restart the dev server, upgrade the dev user to plus (`python -m backend.scripts.grant_plan you@example.com --plan plus`), flip a CV to LaTeX in a REST client, confirm real SVGs and `cache: warm` on the second PUT.

Commit: `feat(latex): compiler setting, engine dispatch, warmth control, .tex export + gate tests`

---

## Phase 6: studio UI for LaTeX mode

### What to implement

1. `frontend/src/api.ts`: `DocSettings` += `compiler: string;`; `AppConfig` += `latex_enabled: boolean;`; `Quota`/`Me` += `latex: boolean` (mirrors `quota_snapshot`); api methods `latexWarmup()`, `latexStatus()`, `latexEndSession(docId)` following the existing `request()` idiom (`api.ts:117-139`).

2. `SettingsPopover.tsx`: second card group under the page-mode cards, same card classes:

- Cards `typst` / `latex` with `t("studio.compiler.typst")` etc. The latex card is locked (lock icon, `opacity-60`, no-op click; copy the template-picker lock pattern `NewJobPanel.tsx:311-333`) when `!config.latex_enabled || !me.quota.latex`, with `t("studio.compiler.latex.locked")` as the description.
- Selecting latex: `updateSettings({...settings, compiler: "latex"})` then fire-and-forget `api.latexWarmup()`. Selecting typst switches back (no warmup).
- When `settings.compiler === "latex"`, the continuous page-mode card renders disabled with `t("studio.pagemode.latexonly")`.
- ApiError with code `latex_locked` -> surface its message under the cards (same small error-text idiom the retry button uses, `index.tsx:133`).

3. Session chip in the Preview toolbar (only when `settings.compiler === "latex"`): small mono chip showing `t("studio.latex.active")` when `latexStatus().warm`, `t("studio.latex.starting")` otherwise (poll every 5 s while not warm, stop when warm); an X button calls `latexEndSession(doc.id)` then shows `t("studio.latex.ended")` transiently. Reuse the pill styling from the job-tab tri-state (`index.tsx:17-20`) rather than inventing chrome.

4. Compile feedback: in latex mode the round-trip is 1.5-3 s warm. `syncing` already drives spinners (`Preview.tsx:88`). Add the missing failure surface in the Preview pane: when `ctl.diagnostics` is non-empty, render a strip above the sheets (both engines benefit; today failures are silent outside the Source tab):

```tsx
{ctl.diagnostics && (
  <div className="mx-6 mb-2 max-h-32 overflow-y-auto rounded-md border border-signal-500/30 bg-signal-950 p-2.5">
    <p className="eyebrow mb-1 text-danger">{t("studio.compile.error")}</p>
    <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-danger/90">{ctl.diagnostics}</pre>
  </div>
)}
```

5. Source tab: when `_is_latex`, the source is `.tex`. Add a hand-rolled StreamLanguage tokenizer next to the Typst one (`SourceEditor.tsx:7-23`), ~12 lines: `%` line comments, `\command` keywords, `{}` brackets, `$` math as string. Chat tab: when latex + source mode, show the disabled notice (reuse the source-banner idiom `EditorPanel.tsx:54-64`) with `t("studio.chat.latexsource")` instead of the input.

6. Download row (`Preview.tsx:90-104`): third anchor to `/api/documents/${doc.id}/source.tex`, icon `FileCode2`, label `t("studio.download.tex")`, rendered only when `settings.compiler === "latex"` (and the `.typ` anchor hides in that case).

7. i18n, all three blocks:

| key | en | fr | de |
|---|---|---|---|
| `studio.compiler.title` | Compiler | Compilateur | Compiler |
| `studio.compiler.typst` | Typst | Typst | Typst |
| `studio.compiler.typst.desc` | Instant preview (default) | Aperçu instantané (défaut) | Sofortige Vorschau (Standard) |
| `studio.compiler.latex` | LaTeX | LaTeX | LaTeX |
| `studio.compiler.latex.desc` | Real XeLaTeX with .tex export, kept warm | Vrai XeLaTeX avec export .tex, gardé au chaud | Echtes XeLaTeX mit .tex-Export, warm gehalten |
| `studio.compiler.latex.locked` | Needs Plus or Pro | Nécessite Plus ou Pro | Erfordert Plus oder Pro |
| `studio.pagemode.latexonly` | Continuous needs the Typst compiler | Le mode continu nécessite Typst | Fortlaufend erfordert den Typst-Compiler |
| `studio.latex.active` | LaTeX warm | LaTeX chaud | LaTeX warm |
| `studio.latex.starting` | LaTeX starting… | Démarrage LaTeX… | LaTeX startet… |
| `studio.latex.ended` | Session cache cleared | Cache de session vidé | Sitzungs-Cache geleert |
| `studio.latex.end` | End session | Terminer la session | Sitzung beenden |
| `studio.chat.latexsource` | Chat is off while hand-editing LaTeX. Revert to guided editing to use it. | Le chat est coupé pendant l'édition LaTeX. Revenez au mode guidé. | Chat ist beim LaTeX-Editieren aus. Zurück zum geführten Modus. |
| `studio.download.tex` | .tex | .tex | .tex |

### Tests + validation

```bash
cd frontend && npm test && npm run build
```

Browser verification with the full local stack (compose latexc up, `.env` pointing at it, plus-plan dev user): flip compiler to LaTeX, watch the chip go starting -> warm, confirm SVG preview updates, hand-edit the `.tex` in the Source tab and confirm recompile + diagnostics on an injected error (`\errmessage{x}`), download `.tex` and PDF, End session, switch back to Typst. Screenshot each state. If a hidden-pane click refuses to land, use the JS fallback pattern noted in memory (`studio-intensity-loading`).

Commit: `feat(latex): studio compiler cards, session chip, tex source editing + i18n`

---## Phase 7: production rollout + ops

### What to implement

1. `ops/latexc.py` (new, ~200 lines; decision 5). Imports the pure helpers from `ops.deploy` (`gcloud_json`, `gcloud_stream`, `http_get`, `git_sha`, `candidate_tag`) and declares its own config block at the top, same style as `deploy.py:42-75`:

```python
PROJECT = os.environ.get("GCP_PROJECT_ID", "project-60fad876-6da7-41f3-bfd")
REGION = os.environ.get("GCP_REGION", "europe-west1")
SERVICE = "cvglowup-latexc"
IMAGE = f"{REGION}-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/{SERVICE}"
MEMORY = "2Gi"
CPU = "1"
CONCURRENCY = "2"
MIN_INSTANCES = "0"   # cold by default; warmth is toggled at runtime (on/off/warmup)
MAX_INSTANCES = "2"
TIMEOUT = "120"
SECRETS = {"LATEXC_TOKEN": "LATEXC_TOKEN:latest"}
```

Subcommands:

- `deploy`: `gcloud builds submit --config services/latexc/cloudbuild.yaml --substitutions _IMAGE={IMAGE}:{sha}` then `gcloud run deploy {SERVICE} --image ... --no-traffic --tag cand-{sha} --allow-unauthenticated --session-affinity --memory/--cpu/--concurrency/--min-instances/--max-instances/--timeout --set-secrets ...`, smoke the tagged URL, promote traffic, smoke again. Smoke = `GET /v1/status` with the token (fetched via `gcloud secrets versions access`, the `grant_plan.py:37-54` pattern) + one probe `POST /v1/compile` asserting `ok` and `%PDF`.
- `on` / `off`: `gcloud run services update {SERVICE} --min-instances 1|0` + print the resulting state. **`off` is the manual off-switch for prod.**
- `status`: describe the service, print min-instances, latest revision, plus estimated idle cost line (`$0` at 0, `~$8/mo` at 1).
- `rollback`: traffic shift to the previous READY revision (reuse `rollback_target` from deploy.py).

2. Auth model: the service is reachable (`--allow-unauthenticated` at the Cloud Run layer) and `LATEXC_TOKEN` is the boundary; every route 401s without the bearer. This keeps the local and prod call paths identical. Cloud Run IAM ID-token auth is the documented follow-up hardening, not v1.

3. App-service config: add to `ops/deploy.py` declaration block (config is code): `ENV_VARS["LATEXC_URL"] = f"https://{...}"` (the stable service URL printed by `ops/latexc.py status`), `ENV_VARS["LATEXC_SERVICE"] = "cvglowup-latexc"`, and `SECRETS["LATEXC_TOKEN"] = "LATEXC_TOKEN:latest"`. Update the pinned assertions in `ops/tests/test_deploy.py:141-235` (the 5 tests that enumerate env/secret sets) in the same commit.

4. One-time GCP setup (document in `docs/deploy.md`, Ayman runs these, they touch IAM/secrets):

```bash
# secret for the shared token
python - <<'EOF'
import secrets; print(secrets.token_urlsafe(32))
EOF
gcloud secrets create LATEXC_TOKEN --replication-policy automatic --project <PROJECT>
# paste the token when prompted:
gcloud secrets versions add LATEXC_TOKEN --data-file=- --project <PROJECT>
# both services' runtime SA needs to read it (same SA the app already uses for other secrets)
gcloud secrets add-iam-policy-binding LATEXC_TOKEN --member serviceAccount:<RUNTIME_SA> --role roles/secretmanager.secretAccessor
# the app must flip min-instances on the latexc service (warmup + reaper)
gcloud run services add-iam-policy-binding cvglowup-latexc --region europe-west1 \
  --member serviceAccount:<RUNTIME_SA> --role roles/run.developer
```

5. CI/CD: new `.github/workflows/deploy-latexc.yml` (workflow_dispatch, own concurrency group `deploy-cvglowup-latexc`, same auth chain as `deploy.yml:61-82`, final step `python ops/latexc.py deploy`). Extend `ci.yml` with the latexc container-test job from Phase 4. Add `ops/tests/test_latexc_ops.py` unit tests for the new pure decision bits (image tag composition, deploy arg list, cost line).

6. Docs: `services/latexc/README.md` (already written in Phase 4, add the prod section), `docs/deploy.md` new "latexc" section (deploy, on/off, cost, one-time IAM), and update the `cvglowup-runbook` skill (local compose up/down commands, the 8021 port, the off-switch).

### Rollout order

1. Ship the latexc service dark: `python ops/latexc.py deploy` (min 0, no app pointing at it). Smoke passes.
2. Add LATEXC env/secret to the app spec and `python ops/deploy.py deploy`. `/api/config` now says `latex_enabled: true`; UI shows the option to plus/pro.
3. Flip your own account to plus, run the full studio flow against prod once (warmup latency on the very first compile after scale-up is the instance boot + probe, expect 20-40 s; the chip shows "starting").
4. `python ops/latexc.py off` and confirm the reaper/manual-off behavior and that the studio degrades cleanly (compile errors surface in the new Preview strip, docs stay intact).

### Validation

```bash
python ops/latexc.py deploy && python ops/latexc.py status
python ops/deploy.py deploy
python ops/latexc.py off && python ops/latexc.py status
cd backend && python -m pytest ../ops/tests -q
```

Commit: `ops(latexc): candidate/promote deploy script, warm on/off switch, CI + docs`

---

## Outcomes and measurement

- **Page mode**: adoption is countable (`SELECT count(*) FROM documents WHERE json_extract(settings,'$.page_mode')='continuous'` on SQLite, `settings->>'page_mode'` on PG). Zero regressions proven by the untouched `pages == 1` goldens plus the three new tests. Preview parity visible in the Phase 2 screenshots.
- **LaTeX mode**: every `LatexCompileOut.timings_ms` is logged by the backend as one structured line (`latex_compile doc=<id> cache=warm total_ms=...`), giving p95 warm compile (< 2500 ms target), cold-start frequency, and cache hit rate straight from logs. Adoption: documents with `compiler='latex'`, upgrade conversions on the locked card (`latex_locked` 403 count). Cost ceiling: min-instances is only ever 0 or 1 and `ops/latexc.py status` prints the current burn.
- **Parity eval** (periodic lane, needs the container): `backend/evals/latex_parity.py` renders the fixture CV through both engines, extracts text with `pypdf` (already in requirements-dev), and asserts token coverage of the LaTeX PDF vs the Typst PDF >= 0.95 plus equal section-label sets in all three languages. Run it before enabling the feature in prod and after any template edit; it is the drift alarm between `cv_onyx.typ` and `tex_onyx.py`.

## Cost and effort

| item | number |
|---|---|
| latexc warm (min-instances=1, 1 vCPU + 2 GiB idle) | ~$7-9 / month while on, $0 while off |
| latexc image | ~1 GB (measured in Phase 4), built by Cloud Build |
| warm compile budget | < 2.5 s p95 (compile + pdf->svg convert) |
| cold path (service off, first compile) | 20-40 s once, then warm |
| effort | P1 0.5d, P2 0.5d, P3 1d, P4 1.5d, P5 1d, P6 1d, P7 1d = ~6.5 focused days |

## Risks and honest caveats

- A continuous PDF prints badly by definition; the card copy says "best shared digitally" on purpose. The 14400 pt reader ceiling is ~17 A4 pages of content; no guard in v1 beyond the copy.
- `pdftocairo` SVGs are heavier than Typst SVGs (path-rendered text). If a page exceeds ~1 MB the preview still works but transfers grow; measure in Phase 4 and consider `-r 150` rasterized fallback only if real numbers demand it.
- The LaTeX template is a port, not a pixel clone. The parity eval catches content drift; small typographic differences are expected and fine (users choosing LaTeX want LaTeX).
- Compiles on `/api/documents/*` remain unmetered (pre-existing). The latexc semaphore (2), per-doc lock, 40 s timeout, and plan gate bound the damage; per-user compile metering is a named follow-up, not v1.
- The bench's "do not swap the engine" verdict stands: Typst stays the default for everyone; LaTeX is an opt-in lane that pays its own warmth.
