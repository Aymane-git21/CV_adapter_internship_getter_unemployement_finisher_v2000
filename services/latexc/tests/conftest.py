"""latexc integration tests. These run INSIDE the container (real TeX Live,
real poppler): docker compose -f services/latexc/compose.yml run --rm latexc
python -m pytest /srv/latexc/tests -q"""
import base64
import os

import httpx
import pytest

TOKEN = "test-token"


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LATEXC_TOKEN", TOKEN)
    monkeypatch.setenv("COMPILE_ROOT", str(tmp_path / "compiles"))
    from latexc.app import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://latexc.test",
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=120,
    ) as c:
        yield c


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def probe_source() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "probe.tex"), encoding="utf-8") as f:
        return f.read()


def compile_body(doc_id: str, source: str, **over) -> dict:
    body = {
        "doc_id": doc_id,
        "files": [{"path": "main.tex", "content_b64": b64(source)}],
    }
    body.update(over)
    return body
