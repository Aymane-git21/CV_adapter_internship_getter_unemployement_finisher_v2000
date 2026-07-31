import base64
import re

from .conftest import b64, compile_body, probe_source


async def test_compile_probe_cold_then_hit_then_warm(client):
    body = compile_body("doc1", probe_source())

    r = await client.post("/v1/compile", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"], out.get("error_line") or out.get("log_tail")
    assert out["cache"] == "cold"
    assert out["pages"] == 1
    assert base64.b64decode(out["pdf_b64"]).startswith(b"%PDF")
    assert out["svgs"] and out["svgs"][0].lstrip().startswith(("<?xml", "<svg"))
    assert out["timings_ms"]["total"] > 0

    # identical content: served from the content-addressed cache, no TeX run
    r = await client.post("/v1/compile", json=body)
    out2 = r.json()
    assert out2["ok"] and out2["cache"] == "hit"
    assert out2["pdf_b64"] == out["pdf_b64"]

    # changed content in an existing project dir: warm recompile (aux reuse)
    changed = compile_body("doc1", probe_source().replace("Warm boot probe", "Warm boot probe v2"))
    r = await client.post("/v1/compile", json=changed)
    out3 = r.json()
    assert out3["ok"] and out3["cache"] == "warm"
    assert out3["pdf_b64"] != out["pdf_b64"]


async def test_fill_probe_line_lands_in_log(client):
    # tex_onyx appends this AtEndDocument probe; the backend fit loop parses
    # CVGFILL:<pagetotal>/<pagegoal> from log_tail. Pin that the log actually
    # carries it end to end through latexmk.
    probed = probe_source().replace(
        r"\begin{document}",
        "\\AtEndDocument{\\typeout{CVGFILL:\\the\\pagetotal/\\the\\pagegoal}}\n\\begin{document}",
    )
    r = await client.post("/v1/compile", json=compile_body("doc-fill", probed))
    out = r.json()
    assert out["ok"], out.get("error_line") or out.get("log_tail")
    m = re.search(r"CVGFILL:([0-9.]+)pt/([0-9.]+)pt", out["log_tail"])
    assert m, "probe line missing from log tail"
    assert float(m.group(2)) > 0


async def test_compile_error_reports_line(client):
    bad = probe_source().replace(r"\begin{document}", "\\begin{document}\n\\errmessage{boom}")
    r = await client.post("/v1/compile", json=compile_body("doc-err", bad))
    out = r.json()
    assert r.status_code == 200
    assert not out["ok"]
    assert out["error_line"] and "boom" in out["error_line"]
    assert out["log_tail"]


async def test_want_svgs_false_skips_svgs(client):
    r = await client.post("/v1/compile", json=compile_body("doc-nosvg", probe_source(), want_svgs=False))
    out = r.json()
    assert out["ok"] and out["svgs"] == [] and out["pdf_b64"]


async def test_status_endpoint(client):
    await client.post("/v1/compile", json=compile_body("doc-status", probe_source()))
    r = await client.get("/v1/status")
    assert r.status_code == 200
    s = r.json()
    assert s["ok"] and s["version"] == "1"
    assert s["projects"] >= 1 and s["disk_mb"] >= 0


async def test_clear_project(client):
    await client.post("/v1/compile", json=compile_body("doc-clear", probe_source()))
    r = await client.delete("/v1/project/doc-clear")
    assert r.status_code == 204
    # next compile of the same doc is cold again
    r = await client.post("/v1/compile", json=compile_body("doc-clear", probe_source()))
    assert r.json()["cache"] == "cold"


async def test_multifile_and_stale_file_removal(client, tmp_path):
    main = probe_source().replace(r"\end{document}", "\\input{extra.tex}\n\\end{document}")
    body = {
        "doc_id": "doc-multi",
        "files": [
            {"path": "main.tex", "content_b64": b64(main)},
            {"path": "extra.tex", "content_b64": b64("Extra content line.\n")},
        ],
    }
    r = await client.post("/v1/compile", json=body)
    assert r.json()["ok"], r.json().get("log_tail")

    # re-send without extra.tex referencing it -> stale file was deleted -> error
    body2 = compile_body("doc-multi", main)
    r = await client.post("/v1/compile", json=body2)
    assert not r.json()["ok"]
