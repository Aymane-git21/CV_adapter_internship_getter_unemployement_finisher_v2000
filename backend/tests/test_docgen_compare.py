"""Gate tests for the docgen comparison bench: pure logic, no network, no
subprocesses, no LLM calls. The paid lane is the bench itself
(python -m backend.evals.docgen_compare)."""
import asyncio
import json
from pathlib import Path

import pytest

from backend.evals.docgen_compare import fidelity, llm, reportgen, runner
from backend.evals.docgen_compare.pipelines import CompileOutcome
from backend.evals.docgen_compare.runner import EditCase, Trial

FIXTURE = Path(__file__).parent / "fixtures" / "sample_cv.json"


# ---------------------------------------------------------------------------
# fidelity
# ---------------------------------------------------------------------------


def test_normalize_folds_ligatures_and_whitespace():
    assert fidelity.normalize("ﬁne-tuning  \n LoRA") == "fine-tuning lora"


def test_score_counts_missing_tokens():
    text = "Alex Martin worked at Lumina AI and INRIA"
    s, missing = fidelity.score(text, ["Alex Martin", "Lumina AI", "Nexa Retail Group"])
    assert s == pytest.approx(2 / 3)
    assert missing == ["Nexa Retail Group"]


def test_required_tokens_from_fixture():
    cv = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tokens = fidelity.required_tokens(cv)
    for expected in ("Alex Martin", "Lumina AI", "Université Grenoble Alpes", "OpenRecruit"):
        assert expected in tokens
    assert len(tokens) >= 10


def test_appears_before():
    assert fidelity.appears_before("Grenoble first, Lumina later", "Grenoble", "Lumina")
    assert not fidelity.appears_before("Lumina first, Grenoble later", "Grenoble", "Lumina")
    assert not fidelity.appears_before("only Grenoble here", "Grenoble", "Lumina")


# ---------------------------------------------------------------------------
# error taxonomy + fences
# ---------------------------------------------------------------------------


def test_classify_error_buckets():
    assert runner.classify_error("! Undefined control sequence.\\l.12 \\entryy") == "latex-undefined-command"
    assert runner.classify_error("error: unknown variable: acent") == "typst-unknown-identifier"
    assert runner.classify_error("error: unclosed delimiter") == "typst-syntax"
    assert runner.classify_error("compilation timed out after 60s") == "timeout"
    assert runner.classify_error("") == ""
    assert runner.classify_error("gibberish nobody recognises") == "other"


def test_strip_fences():
    assert llm.strip_fences("```typst\nhello\n```") == "hello\n"
    assert llm.strip_fences("hello") == "hello\n"


# ---------------------------------------------------------------------------
# semantic checks
# ---------------------------------------------------------------------------


def test_check_semantic_kinds():
    order = EditCase("o", "", "pdf_order", ("Université Grenoble Alpes", "Lumina AI"))
    assert runner.check_semantic(order, "", "Université Grenoble Alpes then Lumina AI")
    assert not runner.check_semantic(order, "", "Lumina AI then Université Grenoble Alpes")
    lacks = EditCase("l", "", "pdf_lacks", ("Nexa Retail Group",))
    assert runner.check_semantic(lacks, "", "clean text")
    assert not runner.check_semantic(lacks, "", "still shows Nexa Retail Group")
    contains = EditCase("c", "", "pdf_contains", ("GitHub Actions",))
    assert runner.check_semantic(contains, "", "Migrated the CI pipeline to GitHub Actions")
    src = EditCase("s", "", "source_contains", ("0E8A66",))
    assert runner.check_semantic(src, 'accent = rgb("#0e8a66")', "")
    compile_only = EditCase("k", "", "compile_only")
    assert runner.check_semantic(compile_only, "", "")


# ---------------------------------------------------------------------------
# runner flows with stubbed pipeline + FakeLLM (no subprocess, no LLM)
# ---------------------------------------------------------------------------


class StubPipeline:
    name = "stub"
    ext = ".typ"
    label = "Stub"
    notes = "STUB NOTES"

    def __init__(self, outcomes: list[bool], ref: Path | None = None):
        self._outcomes = list(outcomes)
        self.ref = ref

    async def compile(self, workdir: Path, filename: str) -> CompileOutcome:
        ok = self._outcomes.pop(0)
        pdf = None
        if ok:
            pdf = workdir / "out.pdf"
            pdf.write_bytes(b"%PDF-1.4 stub")
        return CompileOutcome(ok=ok, ms=7, pdf=pdf, diagnostics="" if ok else "error: unclosed delimiter")


@pytest.fixture()
def patched_pdf_text(monkeypatch):
    monkeypatch.setattr(
        fidelity, "pdf_text_pages",
        lambda path: ("Alex Martin at Lumina AI. Migrated the CI pipeline to GitHub Actions.", 1),
    )


def test_author_repair_flow(tmp_path, patched_pdf_text):
    pipe = StubPipeline([False, True])  # first compile fails, repair compiles
    fake = llm.FakeLLM(["broken source", "fixed source"])
    trials = asyncio.run(
        runner.run_author(pipe, fake, "{}", ["Alex Martin", "Lumina AI"], 1, tmp_path, lambda m: None)
    )
    t = trials[0]
    assert (t.ok_first, t.ok_final, t.attempts) == (False, True, 2)
    assert t.fidelity == 1.0
    assert t.error_kind == "typst-syntax"
    assert "repair" in fake.prompts[1].lower() or "fails to compile" in fake.prompts[1]
    assert (tmp_path / "pdfs" / "author-stub-1.pdf").exists()
    assert (tmp_path / "sources" / "author-stub-1.typ").read_text(encoding="utf-8").startswith("fixed")


def test_author_llm_failure_is_a_data_point(tmp_path):
    pipe = StubPipeline([True])
    fake = llm.FakeLLM([])  # immediately exhausted -> generate raises
    trials = asyncio.run(runner.run_author(pipe, fake, "{}", ["x"], 1, tmp_path, lambda m: None))
    t = trials[0]
    assert not t.ok_final and t.error_kind == "llm-error"


def test_edit_flow_semantic(tmp_path, patched_pdf_text, monkeypatch):
    ref = tmp_path / "ref.typ"
    ref.write_text('accent = rgb("#0F62FE")', encoding="utf-8")
    monkeypatch.setattr(runner, "EDIT_CASES", [runner.EDIT_CASES[0]])  # accent-color only
    pipe = StubPipeline([True], ref=ref)
    fake = llm.FakeLLM(['accent = rgb("#0E8A66")'])
    trials = asyncio.run(runner.run_edit(pipe, fake, tmp_path, lambda m: None))
    t = trials[0]
    assert t.ok_first and t.semantic is True and t.case == "accent-color"


def test_edit_flow_semantic_failure(tmp_path, patched_pdf_text, monkeypatch):
    ref = tmp_path / "ref.typ"
    ref.write_text('accent = rgb("#0F62FE")', encoding="utf-8")
    monkeypatch.setattr(runner, "EDIT_CASES", [runner.EDIT_CASES[0]])
    pipe = StubPipeline([True], ref=ref)
    fake = llm.FakeLLM(['accent = rgb("#FF0000")'])  # compiled, but wrong color
    trials = asyncio.run(runner.run_edit(pipe, fake, tmp_path, lambda m: None))
    assert trials[0].ok_final and trials[0].semantic is False


# ---------------------------------------------------------------------------
# report generation
# ---------------------------------------------------------------------------


def test_report_writes_all_files(tmp_path):
    trials = [
        Trial(phase="author", pipeline="typst", case="t1", ok_first=True, ok_final=True,
              attempts=1, gen_ms=900, compile_ms=80, pages=1, fidelity=1.0),
        Trial(phase="author", pipeline="tectonic", case="t1", ok_first=False, ok_final=True,
              attempts=2, gen_ms=2100, compile_ms=1400, pages=1, fidelity=0.9,
              missing=["OpenRecruit"], error_kind="latex-undefined-command", diagnostics="!"),
        Trial(phase="edit", pipeline="typst", case="accent-color", ok_first=True, ok_final=True,
              attempts=1, gen_ms=800, compile_ms=75, pages=1, semantic=True),
    ]
    speed = [{"pipeline": "typst", "runs_ms": [60, 62], "median_ms": 61, "min_ms": 60, "max_ms": 62}]
    reportgen.write_all(tmp_path, {"date": "test", "model": "fake", "versions": {"typst": "x"}},
                        trials, speed, {"typst": 40.0})
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "| typst | 61 |" in report.replace("  ", " ")
    assert "1/1" in report and "latex-undefined-command" in report and "OpenRecruit" in report
    lines = (tmp_path / "trials.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(trials) + 1
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["author"]["typst"]["compile_first"] == 1
    assert (tmp_path / "report.html").exists()
