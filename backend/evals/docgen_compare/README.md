# Docgen comparison bench

Answers one question: **if the AI has to write document source directly
(source-mode), which toolchain should CV Glowup bet on?** The app's
structured path (JSON -> deterministic template) is not at stake here; this
bench targets the source-mode flows where Gemini authors or edits markup and
Typst's thin training-data footprint hurts.

## Pipelines

| name | AI writes | compiled by | bet |
|---|---|---|---|
| `typst` | standalone Typst (v0.14) | system `typst` | current approach + primer |
| `quarto` | Quarto markdown (`.qmd`) | `.tools/quarto` (Pandoc -> Typst) | AI writes markdown (massive training data), deterministic conversion |
| `tectonic` | LaTeX (article class) | `.tools/tectonic` (XeTeX) | AI writes LaTeX (massive training data), modern self-contained engine |

## Phases

- **speed** (free, offline): compile the hand-written reference CV
  (`references/ref.*`, same content in all three formats) N times warm,
  report median wall time plus installed-toolchain footprint.
- **author** (paid): CV JSON (`backend/tests/fixtures/sample_cv.json`) ->
  complete document. Metrics: compile-on-first-try, compile after the single
  production-style repair round, one-page rate, and **content fidelity**
  (fraction of required tokens — employers, schools, projects, certs —
  present in the extracted PDF text; catches silently dropped content).
- **edit** (paid): six chat-style edit instructions applied to the reference
  doc (accent color, delete entry, add bullet, bottom line, restyle
  headings, reorder sections). Outcomes are checked on the PDF where the
  outcome is content, on the source where it is styling.

The generate -> compile -> one repair round (with real compiler diagnostics)
-> compile loop mirrors production source-mode exactly
(`backend/app/ai/prompts.py`, `backend/evals/eval_source_edit.py`).

### Fairness contract

Every pipeline gets the same design brief, the same CV JSON, and the same
repair budget. Each format's grounding block is sized to what a production
prompt would realistically carry — Typst gets the largest (an adaptation of
the app's shipped primer) precisely because it needs one; that asymmetry is
part of what is being measured.

## Run

```powershell
# one-time: portable toolchains into .tools/ (gitignored, no admin)
powershell -File backend/evals/docgen_compare/setup_tools.ps1

# free offline speed benchmark
.venv\Scripts\python -m backend.evals.docgen_compare --phases speed

# full run (paid lane: <= trials*2 + 12 Gemini flash calls per pipeline)
.venv\Scripts\python -m backend.evals.docgen_compare --trials 3

# slices
.venv\Scripts\python -m backend.evals.docgen_compare --pipelines typst,tectonic --phases edit
.venv\Scripts\python -m backend.evals.docgen_compare --fake --phases author,speed   # offline smoke
```

Results land in `results/<timestamp>/`: `report.md`, `report.html`
(self-contained, page-1 previews when `pymupdf` is installed — dev-only dep,
deliberately not in requirements.txt), `trials.csv`, `summary.json`, plus
every generated source and PDF. Without `GEMINI_API_KEY` the paid phases
print SKIPPED and the speed phase still runs.

Gate tests (offline, fast): `backend/tests/test_docgen_compare.py`.

## Decision rule

Replace the source-mode language only if a challenger beats `typst` by
**>= 20 points of first-try compile+semantic rate across author+edit** AND
keeps warm compile **<= 3 s median** AND holds fidelity >= typst's. Toolchain
footprint matters for the Docker image and cold starts; weigh it in a tie.

## Results — 2026-07-21 (gemini-3.5-flash, 3 author trials, 6 edit cases, 30 calls)

Compile speed, hand-written reference CV, warm toolchain, 5 runs:

| toolchain | median | min..max | installed footprint |
|---|---:|---:|---:|
| typst 0.14.2 | **187 ms** | 183..189 | 45 MB |
| quarto 1.9.38 | 1590 ms | 1567..1621 | 481 MB |
| tectonic 0.16.9 | 2992 ms | 2956..3025 | 91 MB (+ on-demand package fetches) |

Tectonic cold start (empty cache, first compile ever): **65 s** of package
downloads. AI-authored LaTeX also pulls whatever packages it fancies at
compile time (7.3 s observed on a fresh package mix).

Author (JSON -> complete document):

| pipeline | compile 1st try | after 1 repair | one page | fidelity |
|---|---|---|---|---|
| tectonic | **3/3** | 3/3 | 2/3 | 1.0 |
| quarto | 2/3 | 3/3 | **3/3** | 1.0 |
| typst | 1/3 | 3/3 | 1/3 | 1.0 |

Edit (6 chat-style edits on the reference doc): **18/18 first-try compiles,
18/18 semantic, all three pipelines** — with a format primer in the prompt,
editing an existing well-formed doc separates nobody.

Both Typst author failures were the same parser trap: `_#company_` (the
closing `_` is eaten into the identifier). Quarto's one failure was Typst
syntax inside its raw ```{=typst} escape hatch. The trap is now called out
in the production primer (`backend/app/ai/typst_ref.py`) and this bench's
grounding.

### Reading

- Per the decision rule, no challenger clears the bar: tectonic wins author
  reliability massively (+67 pts first-try) but sits at the 3 s compile
  ceiling with a 16x penalty vs typst, plus runtime package downloads —
  unusable for the live preview and risky on Cloud Run. Quarto is 8.5x
  slower, half a gigabyte, and its escape hatch reintroduces the exact
  failure class it was meant to remove.
- Typst's weaknesses measured here — free-form AUTHORING syntax slips and
  one-page adherence — are both already neutralized in production: the app
  never asks the LLM to author whole documents (JSON -> deterministic
  templates), the repair round recovered 3/3, and one-page fitting is the
  renderer's density/font-scale loop, not the LLM's job.
- If AI-authored bespoke layouts ever become a feature, author them in
  Quarto markdown and render through Typst; do not swap the engine.
