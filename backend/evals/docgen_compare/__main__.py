"""Docgen comparison bench CLI.

Paid lane (live Gemini calls): up to trials*2 calls per pipeline for the
author phase plus 12 per pipeline for the edit phase. The speed phase is
free and offline. Without a GEMINI_API_KEY the LLM phases are skipped and
the speed phase still runs (mirrors eval_source_edit's SKIPPED behavior).

Examples:
  python -m backend.evals.docgen_compare                       # everything
  python -m backend.evals.docgen_compare --phases speed        # free, offline
  python -m backend.evals.docgen_compare --pipelines typst,tectonic --trials 5
  python -m backend.evals.docgen_compare --fake --phases author,speed  # harness smoke
"""
import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

from backend.app.config import get_settings

from . import fidelity, reportgen, runner
from .llm import FakeLLM, LiveLLM
from .pipelines import PIPELINES, tool_version, toolchain_footprints

PKG = Path(__file__).resolve().parent
FIXTURE = PKG.parents[1] / "tests" / "fixtures" / "sample_cv.json"


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="docgen_compare")
    ap.add_argument("--phases", default="speed,author,edit",
                    help="comma list of: speed,author,edit")
    ap.add_argument("--pipelines", default="typst,quarto,tectonic")
    ap.add_argument("--trials", type=int, default=3, help="author trials per pipeline")
    ap.add_argument("--speed-runs", type=int, default=5)
    ap.add_argument("--model", default="", help="override GEMINI_MODEL")
    ap.add_argument("--fake", action="store_true",
                    help="offline harness smoke: references as canned LLM output")
    ap.add_argument("--out", default="", help="output dir (default results/<timestamp>)")
    ap.add_argument("--input", default="", help="CV JSON file (default tests fixture)")
    return ap.parse_args(argv)


async def main(argv: list[str]) -> int:
    args = parse_args(argv)
    phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    wanted = [p.strip() for p in args.pipelines.split(",") if p.strip()]
    outdir = Path(args.out) if args.out else PKG / "results" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir.mkdir(parents=True, exist_ok=True)

    pipes = []
    for name in wanted:
        pipe = PIPELINES.get(name)
        if pipe is None:
            print(f"unknown pipeline: {name}")
            return 2
        if pipe.available() is None:
            print(f"SKIP {name}: toolchain not installed "
                  f"(run backend/evals/docgen_compare/setup_tools.ps1)")
            continue
        pipes.append(pipe)
    if not pipes:
        print("no usable pipelines")
        return 2

    cv_path = Path(args.input) if args.input else FIXTURE
    cv = json.loads(cv_path.read_text(encoding="utf-8"))
    cv_json = json.dumps(cv, indent=1, ensure_ascii=False)
    tokens = fidelity.required_tokens(cv)

    settings = get_settings()
    model = args.model or settings.gemini_model
    llm = None
    if args.fake:
        # Author trials replay the hand-written references (pipeline-major
        # order, matching the run loop); the edit phase is not meaningful
        # offline, so it is dropped.
        phases = [p for p in phases if p != "edit"]
        llm = FakeLLM([p.ref.read_text(encoding="utf-8") for p in pipes for _ in range(args.trials)])
        model = "fake"
    elif not settings.gemini_api_key:
        if any(p in phases for p in ("author", "edit")):
            print("SKIPPED author/edit: no GEMINI_API_KEY configured (speed still runs).")
        phases = [p for p in phases if p == "speed"]
    else:
        llm = LiveLLM(settings.gemini_api_key, model)

    print(f"pipelines: {', '.join(p.name for p in pipes)} | phases: {', '.join(phases)} "
          f"| model: {model} | out: {outdir}")

    versions = {}
    for pipe in pipes:
        versions[pipe.name] = await tool_version(pipe.available())
    for tool, ver in versions.items():
        print(f"  {tool}: {ver}")

    log = lambda msg: print(msg, flush=True)  # noqa: E731
    trials: list[runner.Trial] = []
    speed_rows: list[dict] = []

    if "speed" in phases:
        print("— speed phase")
        for pipe in pipes:
            speed_rows.append(await runner.run_speed(pipe, args.speed_runs, outdir, log))
    if "author" in phases and llm is not None:
        print("— author phase")
        for pipe in pipes:
            trials += await runner.run_author(pipe, llm, cv_json, tokens, args.trials, outdir, log)
    if "edit" in phases and llm is not None:
        print("— edit phase")
        for pipe in pipes:
            trials += await runner.run_edit(pipe, llm, outdir, log)

    meta = {
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "trials": args.trials,
        "speed_runs": args.speed_runs,
        "llm_calls": getattr(llm, "calls", 0),
        "versions": versions,
        "input": str(cv_path),
    }
    reportgen.write_all(outdir, meta, trials, speed_rows, toolchain_footprints())
    print(f"\nwrote {outdir / 'report.md'}, report.html, trials.csv, summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
