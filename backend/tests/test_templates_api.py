"""Gate tests for the read-only template source endpoint (studio code viewer)."""


async def test_template_source_served(client):
    r = await client.get("/api/templates/typst/cv_onyx.typ")
    assert r.status_code == 200
    assert "render" in r.text and "set page" in r.text


async def test_template_source_common_served(client):
    r = await client.get("/api/templates/typst/common.typ")
    assert r.status_code == 200
    assert "density-params" in r.text


async def test_template_source_unknown_404(client):
    r = await client.get("/api/templates/typst/nope.typ")
    assert r.status_code == 404


async def test_template_source_bad_names_rejected(client):
    for name in ("..%2Fsecrets.typ", "..evil.typ", "fonts", "cv_onyx.TYP", "a.b.typ"):
        r = await client.get(f"/api/templates/typst/{name}")
        assert r.status_code in (404, 422), name
