"""Aggregate bench trials into report.md, report.html, trials.csv, summary.json.

PNG previews use PyMuPDF when available (dev-only dependency, deliberately
NOT in requirements.txt); without it the HTML report simply has no previews.
"""
import base64
import csv
import statistics
from collections import Counter
from dataclasses import asdict, fields
from pathlib import Path

from .runner import Trial

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None


def _rate(hits: int, n: int) -> str:
    return f"{hits}/{n}" if n else "-"


def agg_author(trials: list[Trial]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted({t.pipeline for t in trials}):
        rows = [t for t in trials if t.pipeline == p]
        ok = [t for t in rows if t.ok_final]
        fids = [t.fidelity for t in ok if t.fidelity is not None]
        out[p] = {
            "n": len(rows),
            "compile_first": sum(t.ok_first for t in rows),
            "compile_final": sum(t.ok_final for t in rows),
            "one_page": sum(t.pages == 1 for t in ok),
            "fidelity_mean": round(sum(fids) / len(fids), 3) if fids else None,
            "gen_ms_mean": int(sum(t.gen_ms for t in rows) / len(rows)) if rows else 0,
            "compile_ms_median": int(statistics.median(t.compile_ms for t in ok)) if ok else None,
        }
    return out


def agg_edit(trials: list[Trial]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted({t.pipeline for t in trials}):
        rows = [t for t in trials if t.pipeline == p]
        out[p] = {
            "n": len(rows),
            "compile_first": sum(t.ok_first for t in rows),
            "compile_final": sum(t.ok_final for t in rows),
            "semantic": sum(bool(t.semantic) for t in rows),
        }
    return out


def error_counts(trials: list[Trial]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for t in trials:
        if t.error_kind:
            out.setdefault(t.pipeline, Counter())[t.error_kind] += 1  # type: ignore[assignment]
    return {p: dict(c) for p, c in out.items()}


def _png_data_uri(pdf_path: Path, zoom: float = 1.5) -> str | None:
    if fitz is None or not pdf_path.exists():
        return None
    with fitz.open(pdf_path) as doc:
        if doc.page_count == 0:
            return None
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return "data:image/png;base64," + base64.b64encode(pix.tobytes("png")).decode()


def write_all(
    outdir: Path,
    meta: dict,
    trials: list[Trial],
    speed_rows: list[dict],
    footprints: dict[str, float],
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    author = agg_author([t for t in trials if t.phase == "author"])
    edit = agg_edit([t for t in trials if t.phase == "edit"])
    errors = error_counts(trials)

    # ---- trials.csv --------------------------------------------------------
    cols = [f.name for f in fields(Trial)]
    with (outdir / "trials.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for t in trials:
            d = asdict(t)
            d["missing"] = "; ".join(d["missing"])
            w.writerow([d[c] for c in cols])

    # ---- summary.json ------------------------------------------------------
    import json

    (outdir / "summary.json").write_text(
        json.dumps(
            {"meta": meta, "author": author, "edit": edit, "speed": speed_rows,
             "footprints_mb": footprints, "error_buckets": errors},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ---- report.md ---------------------------------------------------------
    md: list[str] = [f"# Docgen comparison — {meta.get('date', '')}", ""]
    md += [f"- model: `{meta.get('model', '-')}`, trials per pipeline: {meta.get('trials', '-')}, "
           f"LLM calls: {meta.get('llm_calls', '-')}"]
    for tool, ver in meta.get("versions", {}).items():
        md += [f"- {tool}: {ver}"]
    md += ["", "## Compile speed (hand-written reference CV, warm toolchain)", "",
           "| toolchain | median ms | min ms | max ms | footprint MB |",
           "|---|---:|---:|---:|---:|"]
    for row in speed_rows:
        if "error" in row:
            md += [f"| {row['pipeline']} | FAILED | - | - | {footprints.get(row['pipeline'], '-')} |"]
        else:
            md += [f"| {row['pipeline']} | {row['median_ms']} | {row['min_ms']} | {row['max_ms']} "
                   f"| {footprints.get(row['pipeline'], '-')} |"]
    if author:
        md += ["", "## Author phase — CV JSON to complete document, one repair round allowed", "",
               "| pipeline | compile 1st try | compile final | one page | fidelity | median compile ms | mean gen ms |",
               "|---|---|---|---|---|---:|---:|"]
        for p, a in author.items():
            md += [f"| {p} | {_rate(a['compile_first'], a['n'])} | {_rate(a['compile_final'], a['n'])} "
                   f"| {_rate(a['one_page'], a['compile_final'])} "
                   f"| {a['fidelity_mean'] if a['fidelity_mean'] is not None else '-'} "
                   f"| {a['compile_ms_median'] if a['compile_ms_median'] is not None else '-'} "
                   f"| {a['gen_ms_mean']} |"]
    if edit:
        md += ["", "## Edit phase — chat-style edits on the reference doc, one repair round allowed", "",
               "| pipeline | compile 1st try | compile final | semantic pass |",
               "|---|---|---|---|"]
        for p, e in edit.items():
            md += [f"| {p} | {_rate(e['compile_first'], e['n'])} | {_rate(e['compile_final'], e['n'])} "
                   f"| {_rate(e['semantic'], e['n'])} |"]
    if errors:
        md += ["", "## First-attempt compile-failure buckets", ""]
        for p, buckets in errors.items():
            for b, n in sorted(buckets.items(), key=lambda kv: -kv[1]):
                md += [f"- {p}: {b} ×{n}"]
    misses = [t for t in trials if t.phase == "author" and t.fidelity is not None and t.fidelity < 1.0]
    if misses:
        md += ["", "## Dropped content (author trials with fidelity < 1.0)", ""]
        for t in misses:
            md += [f"- {t.pipeline} {t.case}: missing {', '.join(t.missing)}"]
    (outdir / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # ---- report.html (self-contained, with page-1 previews) ----------------
    html: list[str] = [
        "<meta charset='utf-8'><title>Docgen comparison</title>",
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;max-width:1200px}"
        "table{border-collapse:collapse;margin:1rem 0}td,th{border:1px solid #ccc;"
        "padding:4px 10px;font-size:14px}th{background:#f4f4f4}figure{margin:0}"
        "figcaption{font-size:12px;text-align:center;padding:4px}"
        ".grid{display:flex;flex-wrap:wrap;gap:12px}.grid img{width:260px;border:1px solid #ddd}"
        "</style>",
        f"<h1>Docgen comparison — {meta.get('date', '')}</h1>",
        "<pre>" + "\n".join(f"{k}: {v}" for k, v in meta.get("versions", {}).items()) + "</pre>",
    ]

    def table(title: str, headers: list[str], rows: list[list]) -> None:
        html.append(f"<h2>{title}</h2><table><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")
        for r in rows:
            html.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
        html.append("</table>")

    table("Compile speed (warm)", ["toolchain", "median ms", "min", "max", "footprint MB"],
          [[r["pipeline"], r.get("median_ms", "FAIL"), r.get("min_ms", "-"), r.get("max_ms", "-"),
            footprints.get(r["pipeline"], "-")] for r in speed_rows])
    if author:
        table("Author phase", ["pipeline", "compile 1st", "compile final", "one page", "fidelity",
                               "median compile ms", "mean gen ms"],
              [[p, _rate(a["compile_first"], a["n"]), _rate(a["compile_final"], a["n"]),
                _rate(a["one_page"], a["compile_final"]),
                a["fidelity_mean"] if a["fidelity_mean"] is not None else "-",
                a["compile_ms_median"] if a["compile_ms_median"] is not None else "-",
                a["gen_ms_mean"]] for p, a in author.items()])
    if edit:
        table("Edit phase", ["pipeline", "compile 1st", "compile final", "semantic"],
              [[p, _rate(e["compile_first"], e["n"]), _rate(e["compile_final"], e["n"]),
                _rate(e["semantic"], e["n"])] for p, e in edit.items()])

    previews: list[tuple[str, Path]] = []
    for t in trials:
        if t.artifact:
            previews.append((f"{t.phase} {t.pipeline} {t.case}", outdir / t.artifact))
    if previews:
        html.append("<h2>Page-1 previews</h2>")
        if fitz is None:
            html.append("<p><em>PyMuPDF not installed — run `pip install pymupdf` for previews.</em></p>")
        else:
            html.append("<div class='grid'>")
            for caption, pdf in previews:
                uri = _png_data_uri(pdf)
                if uri:
                    html.append(f"<figure><img src='{uri}' loading='lazy'>"
                                f"<figcaption>{caption}</figcaption></figure>")
            html.append("</div>")
    (outdir / "report.html").write_text("\n".join(html), encoding="utf-8")
