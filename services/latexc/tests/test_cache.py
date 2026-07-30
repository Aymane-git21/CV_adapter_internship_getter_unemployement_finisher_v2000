import asyncio

from .conftest import compile_body, probe_source


async def test_lru_eviction_beyond_project_cap(client, monkeypatch, tmp_path):
    monkeypatch.setenv("LATEXC_MAX_PROJECTS", "2")
    for i in range(3):
        r = await client.post("/v1/compile", json=compile_body(f"evict-{i}", probe_source()))
        assert r.json()["ok"]
        await asyncio.sleep(0.05)  # distinct mtimes for LRU order
    root = tmp_path / "compiles"
    live = sorted(d.name for d in root.iterdir() if d.is_dir())
    assert len(live) == 2
    assert "evict-0" not in live, "oldest project should have been evicted"
    assert "evict-2" in live, "the dir just used must never be evicted"


async def test_concurrent_same_doc_serializes(client):
    body = compile_body("conc", probe_source())
    r1, r2 = await asyncio.gather(
        client.post("/v1/compile", json=body),
        client.post("/v1/compile", json=body),
    )
    outs = [r1.json(), r2.json()]
    assert all(o["ok"] for o in outs)
    # one did the work, the other was served from cache (or both compiled
    # serially); either way the per-doc lock prevented interleaved TeX runs
    assert {o["cache"] for o in outs} <= {"cold", "hit", "warm"}
    assert outs[0]["pdf_b64"] == outs[1]["pdf_b64"]


async def test_aux_state_persists_between_compiles(client, tmp_path):
    await client.post("/v1/compile", json=compile_body("warmdoc", probe_source()))
    pdir = tmp_path / "compiles" / "warmdoc"
    fdb = list(pdir.glob("*.fdb_latexmk"))
    assert fdb, "latexmk file database missing; warm cache would be inert"
    changed = compile_body("warmdoc", probe_source() + "\n% touched\n")
    r = await client.post("/v1/compile", json=changed)
    assert r.json()["cache"] == "warm"
    assert list(pdir.glob("*.fdb_latexmk")), "fdb must survive recompiles"
