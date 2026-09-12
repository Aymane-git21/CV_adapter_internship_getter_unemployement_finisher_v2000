"""SPA serving must survive the states a frontend build leaves dist/ in, and
must never serve a file from outside dist/.

- A rebuild empties dist/ before rewriting it: create_app() raised when dist/
  existed without dist/assets, so the app (and every test that builds it)
  crashed at startup mid-build.
- The catch-all route joined the request path straight onto dist/, so a
  percent-encoded ../ could reach files outside it.
"""
import httpx

from backend.app import main as app_main
from backend.app.config import get_settings


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _dist(root, with_assets: bool):
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True) if with_assets else dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


async def test_app_starts_and_serves_while_dist_has_no_assets(tmp_path, monkeypatch):
    dist = _dist(tmp_path, with_assets=False)
    monkeypatch.setattr(get_settings(), "frontend_dist", dist)

    app = app_main.create_app()
    async with _client(app) as c:
        r = await c.get("/profile")
        assert r.status_code == 200 and "<title>spa</title>" in r.text

        # The build finishes after startup: its assets are still served.
        (dist / "assets").mkdir()
        (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
        r = await c.get("/assets/app.js")
        assert r.status_code == 200 and "console.log" in r.text


async def test_catch_all_never_serves_files_outside_dist(tmp_path, monkeypatch):
    for with_assets in (True, False):
        root = tmp_path / ("with" if with_assets else "without")
        dist = _dist(root, with_assets=with_assets)
        (root / "secret.env").write_text("SECRET_KEY=leak", encoding="utf-8")
        monkeypatch.setattr(get_settings(), "frontend_dist", dist)

        async with _client(app_main.create_app()) as c:
            for probe in ("/..%2Fsecret.env", "/%2E%2E%2Fsecret.env", "/assets/..%2F..%2Fsecret.env"):
                r = await c.get(probe)
                assert "SECRET_KEY" not in r.text, f"{probe} leaked a file outside dist"
            # A NUL byte must fall back to the app shell, not a 500.
            r = await c.get("/index.html%00.js")
            assert r.status_code == 200 and "<title>spa</title>" in r.text
