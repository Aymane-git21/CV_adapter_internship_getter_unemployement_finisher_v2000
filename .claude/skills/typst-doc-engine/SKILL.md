---
name: typst-doc-engine
description: Authoring, compiling, and debugging Typst CV/cover-letter templates for CV Glowup. Use whenever creating or editing document templates, the structured CVData-to-document rendering layer, the in-browser live preview (typst.ts WASM), or the server-side PDF compile step. Replaces the legacy pdflatex/LaTeX pipeline.
---

# Typst Document Engine (CV Glowup)

Typst replaces pdflatex in this project. Compiles run in ~20–100 ms (vs 2–5 s+ for pdflatex) with a ~40 MB toolchain (vs ~3 GB of texlive), which is what makes the Overleaf-style live preview and fast Cloud Run cold starts possible.

## Architecture contract — the LLM never writes markup

The single most important rule: **Gemini outputs structured JSON (`CVData`, `CoverLetterData` schemas), never raw Typst/LaTeX.** Deterministic template code renders JSON → Typst source → PDF. This eliminates the entire class of "LLM hallucinated a command / forgot to escape `&` → compile failed" bugs the legacy pipeline suffered from.

- Templates live in `templates/typst/` as `.typ` files, one folder per design variant.
- Each template exposes one entry function, e.g. `#cv(data)` where `data` is injected as JSON via `#let data = json("data.json")` or sys inputs (`--input data=<json>`; read with `json(bytes(sys.inputs.data))`).
- Template variants must all consume the SAME schema. Photo/no-photo is a boolean in the data plus template handling, not a separate schema.
- User free-text edits happen either (a) on the JSON via the structured form/chatbot, or (b) directly on generated Typst source in the code editor (advanced mode). Mode (b) source is then the source of truth for that document until regenerated.

## Compiling

- Server / local CLI: `typst compile doc.typ out.pdf --root <dir> --font-path <fonts>`. Windows install: `winget install --id Typst.Typst`. In Docker: download the release binary (single static executable) — do NOT apt-install texlive anything.
- Watch mode for template development: `typst watch doc.typ out.pdf`.
- In-browser preview: `@myriaddreamin/typst.ts` (WASM). Renders to SVG — crisper and faster than PDF.js for live preview. Key gotchas:
  - Fonts must be loaded into the WASM world explicitly (bundle the exact .ttf/.otf files the templates use; do not rely on system fonts or browser/server output will differ).
  - Images (user photo) must be added to the compiler's virtual filesystem (`mapShadow`/`addSource`) before compile.
  - Keep one compiler instance alive and reuse it; instantiation is the slow part (~hundreds of ms), incremental compiles are fast.
- Determinism rule: browser preview and server compile MUST use the same template files, same fonts, same Typst version. Pin the Typst version in both `package.json` (typst.ts) and the Dockerfile, and add a CI check that compiles golden data through both paths.

## Typst syntax survival kit (differences from LaTeX)

- Markup mode by default; code mode behind `#`. `#let`, `#set`, `#show` instead of `\newcommand`/preamble.
- `#set page(paper: "a4", margin: (x: 1.2cm, y: 1.2cm))`, `#set text(font: "Inter", size: 10pt, lang: "fr")`.
- Grid/columns: `#grid(columns: (1fr, auto), ...)` replaces `tabular*` hacks.
- Escaping: only a handful of special chars (`# $ * _ @ \``); when rendering user strings from JSON they arrive as Typst *strings* in code mode, so **no escaping is needed at all** — never string-concatenate user text into markup, always pass it as data.
- Images: `#image("photo.jpg", width: 3cm)`. Round photo: clip with `#box(clip: true, radius: 50%, image(...))`.
- Icons: use a bundled icon font (e.g. Font Awesome via `#text(font: "Font Awesome 7 Free", "\u{f095}")`) or inline SVGs — fontawesome5 LaTeX package does not exist here.
- Page fitting: `#set page(height: auto)` gives the standalone-class cropping behavior of the legacy CV.tex; for strict one-page A4, keep fixed height and expose font-size/spacing knobs the generator can tighten.
- Multilingual: `#set text(lang: "fr")` drives hyphenation/quotes; date formatting via `datetime.today().display("[day]/[month]/[year]")`.

## Porting the legacy templates

Legacy `CV.tex` (standalone class, `\entry{}{}{}{}`, `\project{}{}`) and `CoverLetter.tex` (`\makeextraheader`, `\recipientblock`, `\subject`, `\opening`, `\closing`) are the visual reference. Port = reproduce the layout, then parameterize all hardcoded personal data (name, contacts, links — currently hardcoded in both .tex files) into the schema.

## Debugging

- Typst errors are precise (line/col + message) — surface them verbatim to the editor UI as diagnostics; never retry-loop the LLM on compile errors (with the JSON contract there should be none from generation).
- `typst query` can extract document metadata (e.g. page count) — use it to detect overflow beyond one page and trigger the condensing pass.
