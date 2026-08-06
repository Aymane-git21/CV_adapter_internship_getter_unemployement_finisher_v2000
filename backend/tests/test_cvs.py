"""Master-CV delete contract, pinned for the studio's inline delete UI.

The NewJobPanel hover-x calls DELETE /api/cvs/{id} directly (no confirm), so
ownership checks and idempotent 404s are load-bearing product behavior here.
"""
import pytest

from .conftest import SAMPLE_CV_TEXT, unique_email


async def _register(client, email=None):
    r = await client.post(
        "/api/auth/register", json={"email": email or unique_email(), "password": "longpassword1"}
    )
    assert r.status_code == 200
    return r.json()


async def _create_cv(client, name="Main"):
    r = await client.post("/api/cvs", json={"name": name, "raw_text": SAMPLE_CV_TEXT})
    assert r.status_code == 200
    return r.json()


@pytest.mark.anyio
async def test_delete_removes_cv_from_list(client):
    await _register(client)
    kept = await _create_cv(client, "Keep")
    doomed = await _create_cv(client, "Doomed")

    r = await client.delete(f"/api/cvs/{doomed['id']}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    ids = [c["id"] for c in (await client.get("/api/cvs")).json()]
    assert doomed["id"] not in ids
    assert kept["id"] in ids


@pytest.mark.anyio
async def test_delete_is_owner_scoped(client):
    await _register(client)
    cv = await _create_cv(client)

    client.cookies.clear()
    await _register(client)
    r = await client.delete(f"/api/cvs/{cv['id']}")
    assert r.status_code == 404

    client.cookies.clear()


@pytest.mark.anyio
async def test_double_delete_404s(client):
    await _register(client)
    cv = await _create_cv(client)
    assert (await client.delete(f"/api/cvs/{cv['id']}")).status_code == 200
    assert (await client.delete(f"/api/cvs/{cv['id']}")).status_code == 404


@pytest.mark.anyio
async def test_deleting_the_default_leaves_list_servable(client):
    await _register(client)
    first = await _create_cv(client, "First")  # first CV becomes the default
    second = await _create_cv(client, "Second")
    assert first["is_default"] and not second["is_default"]

    assert (await client.delete(f"/api/cvs/{first['id']}")).status_code == 200
    rows = (await client.get("/api/cvs")).json()
    assert [c["id"] for c in rows] == [second["id"]]
    # No implicit default promotion; the frontend falls back to the first row.
    assert rows[0]["is_default"] is False
