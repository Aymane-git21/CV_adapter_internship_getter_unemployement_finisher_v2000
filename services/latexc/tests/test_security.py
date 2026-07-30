from .conftest import TOKEN, b64, compile_body, probe_source


async def test_auth_required(client):
    r = await client.post("/v1/compile", json=compile_body("d", probe_source()),
                          headers={"Authorization": ""})
    assert r.status_code == 401
    r = await client.get("/v1/status", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    r = await client.get("/v1/status", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


async def test_path_traversal_rejected(client):
    for bad in ("../evil.tex", "a/b.tex", "a\\b.tex", ".."):
        body = {"doc_id": "d-path", "files": [{"path": bad, "content_b64": b64("x")}]}
        r = await client.post("/v1/compile", json=body)
        assert r.status_code == 422, f"{bad} was accepted"


async def test_shell_escape_blocked(client, tmp_path):
    src = probe_source().replace(
        r"\begin{document}",
        "\\begin{document}\n\\immediate\\write18{touch pwned.txt}",
    )
    r = await client.post("/v1/compile", json=compile_body("d-shell", src))
    out = r.json()
    root = tmp_path / "compiles" / "d-shell"
    assert not (root / "pwned.txt").exists(), "shell escape executed"
    # whether TeX warns or errors, no shell command may have run
    assert "runsystem" not in out["log_tail"] or "disabled" in out["log_tail"]


async def test_absolute_input_blocked(client):
    src = probe_source().replace(
        r"\end{document}", "\\input{/etc/passwd}\n\\end{document}"
    )
    r = await client.post("/v1/compile", json=compile_body("d-abs", src))
    out = r.json()
    assert not out["ok"], "reading an absolute path outside the jail must fail"


async def test_timeout_kills_runaway(client):
    src = probe_source().replace(
        r"\end{document}", "\\loop\\iftrue\\repeat\n\\end{document}"
    )
    r = await client.post("/v1/compile", json=compile_body("d-loop", src, timeout_s=5))
    out = r.json()
    assert not out["ok"]
    assert out["error_line"] or "timed out" in out["log_tail"]


async def test_oversize_rejected(client):
    big = "x" * 5_000_000
    body = {"doc_id": "d-big", "files": [{"path": "main.tex", "content_b64": b64(big)}]}
    r = await client.post("/v1/compile", json=body)
    assert r.status_code == 422
