"""Bench orchestration: author / edit / speed phases over the pipelines.

The author and edit flows mirror the production source-mode pipeline exactly
(backend/app/routers/documents.py): generate -> compile -> at most ONE repair
round fed with the real compiler diagnostics -> compile.
"""
import shutil
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from . import fidelity, prompts_bench

# ---------------------------------------------------------------------------
# Result row
# ---------------------------------------------------------------------------


@dataclass
class Trial:
    phase: str            # author | edit
    pipeline: str
    case: str             # trial number or edit-case id
    ok_first: bool        # compiled without repair
    ok_final: bool        # compiled after <=1 repair
    attempts: int
    gen_ms: int           # total LLM latency (author + repair)
    compile_ms: int       # final compile wall time
    pages: int
    fidelity: float | None = None
    missing: list[str] = field(default_factory=list)
    semantic: bool | None = None
    error_kind: str = ""  # bucket of the FIRST-attempt failure, "" if clean
    diagnostics: str = ""
    artifact: str = ""    # saved pdf filename, "" if none


# ---------------------------------------------------------------------------
# Compile-failure taxonomy (first-attempt diagnostics, keyword buckets)
# ---------------------------------------------------------------------------

_BUCKETS: list[tuple[str, tuple[str, ...]]] = [
    ("timeout", ("timed out",)),
    ("llm-error", ("llm call failed",)),
    ("latex-undefined-command", ("undefined control sequence",)),
    ("latex-environment", ("ended by \\end", "begin{", "environment undefined")),
    ("latex-math-mode", ("missing $",)),
    ("latex-other", ("! latex error", "emergency stop", "fatal error occurred")),
    ("yaml", ("yaml",)),
    ("typst-unknown-identifier", ("unknown variable", "unknown function", "file not found")),
    ("typst-syntax", ("unclosed", "unexpected", "expected")),
    ("pandoc", ("pandoc",)),
]


def classify_error(diagnostics: str) -> str:
    low = diagnostics.lower()
    if not low.strip():
        return ""
    for bucket, needles in _BUCKETS:
        if any(n in low for n in needles):
            return bucket
    return "other"


# ---------------------------------------------------------------------------
# Edit cases — format-agnostic instructions, outcome checked on the PDF
# where the outcome is content, on the source where it is styling.
# ---------------------------------------------------------------------------


@dataclass
class EditCase:
    id: str
    instruction: str
    kind: str          # source_contains | pdf_contains | pdf_lacks | pdf_order | compile_only
    args: tuple = ()


EDIT_CASES = [
    EditCase(
        "accent-color",
        "Change the accent color used for section headings and rules from #0F62FE to #0E8A66 everywhere.",
        "source_contains",
        ("0E8A66",),
    ),
    EditCase(
        "delete-entry",
        "Delete the Data Scientist experience entry at Nexa Retail Group entirely.",
        "pdf_lacks",
        ("Nexa Retail Group",),
    ),
    EditCase(
        "add-bullet",
        'Add this bullet to the Lumina AI experience entry, as the last bullet: "Migrated the CI pipeline to GitHub Actions".',
        "pdf_contains",
        ("GitHub Actions",),
    ),
    EditCase(
        "bottom-line",
        "Add a thin horizontal rule and the centered text 'References available upon request' at the very bottom of the document.",
        "pdf_contains",
        ("References available upon request",),
    ),
    EditCase(
        "restyle-headings",
        "Make all section headings slightly smaller and give them wider letter spacing.",
        "compile_only",
    ),
    EditCase(
        "reorder-sections",
        "Move the Education section so it appears before the Experience section.",
        "pdf_order",
        ("Université Grenoble Alpes", "Lumina AI"),
    ),
]


def check_semantic(case: EditCase, source: str, pdf_text: str) -> bool:
    if case.kind == "compile_only":
        return True
    if case.kind == "source_contains":
        return case.args[0].lower() in source.lower()
    if case.kind == "pdf_contains":
        return fidelity.normalize(case.args[0]) in fidelity.normalize(pdf_text)
    if case.kind == "pdf_lacks":
        return fidelity.normalize(case.args[0]) not in fidelity.normalize(pdf_text)
    if case.kind == "pdf_order":
        return fidelity.appears_before(pdf_text, case.args[0], case.args[1])
    raise ValueError(f"unknown check kind {case.kind}")


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------


def _write_doc(workdir: Path, fname: str, source: str) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / fname).write_text(source, encoding="utf-8")


def _stage_ref(workdir: Path, ref: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ref, workdir / ref.name)


def _save(outdir: Path, sub: str, name: str, data: bytes | str) -> str:
    d = outdir / sub
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data, encoding="utf-8")
    return str(p.relative_to(outdir))


async def _generate_compile_repair(pipe, llm, first_prompt: str, workdir: Path, log) -> tuple:
    """Shared author/edit core. Returns (trial fields tuple, final source, pdf path)."""
    gen_ms = 0
    try:
        source, ms = await llm.generate(first_prompt)
        gen_ms += ms
    except Exception as exc:  # noqa: BLE001 — a dead LLM call is a data point, not a crash
        return (False, False, 1, gen_ms, 0, "llm call failed: " + str(exc)[:500], None), "", None

    fname = "doc" + pipe.ext
    _write_doc(workdir, fname, source)
    res = await pipe.compile(workdir, fname)
    ok_first, attempts, first_diag = res.ok, 1, res.diagnostics

    if not res.ok:
        try:
            source, ms = await llm.generate(
                prompts_bench.repair_prompt(pipe.label, pipe.notes, source, res.diagnostics)
            )
            gen_ms += ms
            _write_doc(workdir, fname, source)
            res = await pipe.compile(workdir, fname)
            attempts = 2
        except Exception as exc:  # noqa: BLE001
            first_diag = first_diag + " | repair llm failed: " + str(exc)[:300]

    diag = first_diag if not ok_first else ""
    return (ok_first, res.ok, attempts, gen_ms, res.ms, diag, res.pdf), source, res.pdf


async def run_author(pipe, llm, cv_json: str, tokens: list[str], trials: int, outdir: Path, log) -> list[Trial]:
    results = []
    prompt = prompts_bench.author_prompt(pipe.label, pipe.notes, cv_json)
    for i in range(1, trials + 1):
        workdir = outdir / "work" / f"author-{pipe.name}-{i}"
        (ok_first, ok_final, attempts, gen_ms, compile_ms, diag, pdf), source, _ = (
            await _generate_compile_repair(pipe, llm, prompt, workdir, log)
        )
        pages, fid, missing, artifact = 0, None, [], ""
        if source:
            _save(outdir, "sources", f"author-{pipe.name}-{i}{pipe.ext}", source)
        if ok_final and pdf is not None:
            text, pages = fidelity.pdf_text_pages(pdf)
            fid, missing = fidelity.score(text, tokens)
            artifact = _save(outdir, "pdfs", f"author-{pipe.name}-{i}.pdf", pdf.read_bytes())
        t = Trial(
            phase="author", pipeline=pipe.name, case=f"t{i}",
            ok_first=ok_first, ok_final=ok_final, attempts=attempts,
            gen_ms=gen_ms, compile_ms=compile_ms, pages=pages,
            fidelity=fid, missing=missing,
            error_kind=classify_error(diag), diagnostics=diag[:1500], artifact=artifact,
        )
        results.append(t)
        log(f"  author {pipe.name} t{i}: "
            f"{'ok' if ok_first else 'FAIL->' + ('repaired' if ok_final else 'FAIL')}"
            f" pages={pages} fidelity={f'{fid:.2f}' if fid is not None else '-'}"
            f" compile={compile_ms}ms")
        shutil.rmtree(workdir, ignore_errors=True)
    return results


async def run_edit(pipe, llm, trials_outdir: Path, log) -> list[Trial]:
    results = []
    ref_source = pipe.ref.read_text(encoding="utf-8")
    for case in EDIT_CASES:
        workdir = trials_outdir / "work" / f"edit-{pipe.name}-{case.id}"
        prompt = prompts_bench.edit_prompt(pipe.label, pipe.notes, ref_source, case.instruction)
        (ok_first, ok_final, attempts, gen_ms, compile_ms, diag, pdf), source, _ = (
            await _generate_compile_repair(pipe, llm, prompt, workdir, log)
        )
        pages, semantic, artifact = 0, None, ""
        if source:
            _save(trials_outdir, "sources", f"edit-{pipe.name}-{case.id}{pipe.ext}", source)
        if ok_final and pdf is not None:
            text, pages = fidelity.pdf_text_pages(pdf)
            semantic = check_semantic(case, source, text)
            artifact = _save(trials_outdir, "pdfs", f"edit-{pipe.name}-{case.id}.pdf", pdf.read_bytes())
        elif ok_final:
            semantic = check_semantic(case, source, "")
        else:
            semantic = False
        t = Trial(
            phase="edit", pipeline=pipe.name, case=case.id,
            ok_first=ok_first, ok_final=ok_final, attempts=attempts,
            gen_ms=gen_ms, compile_ms=compile_ms, pages=pages, semantic=semantic,
            error_kind=classify_error(diag), diagnostics=diag[:1500], artifact=artifact,
        )
        results.append(t)
        log(f"  edit {pipe.name} {case.id}: "
            f"{'ok' if ok_first else 'FAIL->' + ('repaired' if ok_final else 'FAIL')}"
            f" semantic={'ok' if semantic else 'FAIL'}")
        shutil.rmtree(workdir, ignore_errors=True)
    return results


async def run_speed(pipe, runs: int, outdir: Path, log) -> dict:
    """Compile the hand-written reference `runs` times in fresh dirs, warm
    toolchain. The first run is a discarded warmup."""
    times: list[int] = []
    for i in range(runs + 1):
        workdir = outdir / "work" / f"speed-{pipe.name}-{i}"
        _stage_ref(workdir, pipe.ref)
        res = await pipe.compile(workdir, pipe.ref.name)
        shutil.rmtree(workdir, ignore_errors=True)
        if not res.ok:
            log(f"  speed {pipe.name}: reference failed to compile: {res.diagnostics[:300]}")
            return {"pipeline": pipe.name, "error": res.diagnostics[:1000]}
        if i > 0:
            times.append(res.ms)
    row = {
        "pipeline": pipe.name,
        "runs_ms": times,
        "median_ms": int(statistics.median(times)),
        "min_ms": min(times),
        "max_ms": max(times),
    }
    log(f"  speed {pipe.name}: median {row['median_ms']}ms over {len(times)} runs "
        f"(min {row['min_ms']}, max {row['max_ms']})")
    return row
