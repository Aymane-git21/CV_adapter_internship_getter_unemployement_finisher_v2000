"""Upload endpoints: /api/cvs/upload (PDF -> parsed MasterCV) and /api/photos.

These routes had no coverage and broke intermittently in production:
- photo upload 401'd every guest (require_user on a guest-friendly route)
- PDF magic check rejected valid PDFs with a preamble before %PDF
- filenames longer than 120 chars overflowed MasterCV.name on Postgres
"""
from ..app.ai.fake import FakeProvider
from .conftest import unique_email

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
PDF_WITH_PREAMBLE = b"\xef\xbb\xbfjunk-from-a-weird-generator\n" + PDF_BYTES
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64

# The upload route guards on settings.ai_enabled (false under CVG_FAKE_AI);
# a BYOK header bypasses the guard, and the patched provider ignores the key.
BYOK = {"X-User-Gemini-Key": "test-byok-key-000"}


async def _register(client):
    r = await client.post(
        "/api/auth/register", json={"email": unique_email(), "password": "longpassword1"}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _fake_provider(monkeypatch):
    monkeypatch.setattr(
        "backend.app.routers.cvs.get_provider", lambda byok_key=None: FakeProvider()
    )


# ---- /api/cvs/upload --------------------------------------------------------


async def test_pdf_upload_authed(client, monkeypatch):
    _fake_provider(monkeypatch)
    await _register(client)
    r = await client.post(
        "/api/cvs/upload",
        headers=BYOK,
        files={"file": ("my_cv.pdf", PDF_BYTES, "application/pdf")},
        data={"name": "My CV"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "My CV"
    assert body["is_default"] is True
    assert body["data"]["full_name"]


async def test_pdf_upload_accepts_header_preamble(client, monkeypatch):
    """%PDF may sit anywhere in the first 1024 bytes (PDF spec 7.5.2)."""
    _fake_provider(monkeypatch)
    await _register(client)
    r = await client.post(
        "/api/cvs/upload",
        headers=BYOK,
        files={"file": ("cv.pdf", PDF_WITH_PREAMBLE, "application/pdf")},
    )
    assert r.status_code == 200, r.text


async def test_pdf_upload_clamps_long_filename(client, monkeypatch):
    """MasterCV.name is String(120): Postgres errors on overflow, so clamp."""
    _fake_provider(monkeypatch)
    await _register(client)
    r = await client.post(
        "/api/cvs/upload",
        headers=BYOK,
        files={"file": ("cv.pdf", PDF_BYTES, "application/pdf")},
        data={"name": "x" * 400},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["name"]) <= 120


async def test_pdf_upload_rejects_non_pdf(client, monkeypatch):
    _fake_provider(monkeypatch)
    await _register(client)
    r = await client.post(
        "/api/cvs/upload",
        headers=BYOK,
        files={"file": ("cv.pdf", b"MZ this is not a pdf at all", "application/pdf")},
    )
    assert r.status_code == 415


async def test_pdf_upload_rejects_oversize(client, monkeypatch):
    _fake_provider(monkeypatch)
    await _register(client)
    r = await client.post(
        "/api/cvs/upload",
        headers=BYOK,
        files={"file": ("cv.pdf", b"%PDF" + b"\x00" * (8 * 1024 * 1024), "application/pdf")},
    )
    assert r.status_code == 413


async def test_pdf_upload_requires_auth(client):
    """Uploaded PDFs become MasterCV rows, which need an owner: guests get 401.
    The frontend routes guests to the sign-in modal instead of this call."""
    r = await client.post(
        "/api/cvs/upload", files={"file": ("cv.pdf", PDF_BYTES, "application/pdf")}
    )
    assert r.status_code == 401


async def test_pdf_upload_offline_without_byok_is_explained(client):
    """No AI + no BYOK -> a clear 422, not a confusing parse failure."""
    await _register(client)
    r = await client.post(
        "/api/cvs/upload", files={"file": ("cv.pdf", PDF_BYTES, "application/pdf")}
    )
    assert r.status_code == 422
    assert "paste" in r.json()["detail"].lower()


async def test_create_cv_clamps_long_name(client):
    await _register(client)
    r = await client.post("/api/cvs", json={"name": "y" * 400, "raw_text": "Jane Doe\nEngineer"})
    assert r.status_code == 200, r.text
    assert len(r.json()["name"]) <= 120


# ---- /api/photos --------------------------------------------------------------


async def test_photo_upload_guest(client):
    """Guests generate documents with photos; the route must not require auth."""
    r = await client.post("/api/photos", files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")})
    assert r.status_code == 200, r.text
    photo_id = r.json()["id"]

    r = await client.get(f"/api/photos/{photo_id}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"


async def test_photo_upload_authed_png(client):
    await _register(client)
    r = await client.post("/api/photos", files={"file": ("photo.png", PNG_BYTES, "image/png")})
    assert r.status_code == 200, r.text
    r = await client.get(f"/api/photos/{r.json()['id']}")
    assert r.headers["content-type"] == "image/png"


async def test_photo_upload_rejects_non_image(client):
    r = await client.post("/api/photos", files={"file": ("photo.jpg", b"GIF89a...", "image/gif")})
    assert r.status_code == 415


async def test_photo_upload_rejects_oversize(client):
    r = await client.post(
        "/api/photos",
        files={"file": ("photo.jpg", JPEG_BYTES + b"\x00" * (3 * 1024 * 1024), "image/jpeg")},
    )
    assert r.status_code == 413
