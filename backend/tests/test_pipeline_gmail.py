"""GmailSender: refresh-token -> access-token -> raw send. All HTTP mocked."""
import base64

import httpx

from backend.app.mailer import SEND_URL, TOKEN_URL, GmailSender, build_application_email
from backend.tests.conftest import unique_email


async def test_send_exchanges_token_and_posts_raw():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(TOKEN_URL):
            body = request.content.decode()
            assert "refresh_token=rt-1" in body and "grant_type=refresh_token" in body
            return httpx.Response(200, json={"access_token": "at-9", "expires_in": 3599})
        assert url.startswith(SEND_URL)
        assert request.headers["Authorization"] == "Bearer at-9"
        seen["raw"] = request.content
        return httpx.Response(200, json={"id": "msg-42"})

    msg = build_application_email("a@b.c", "hr@co.fr", "Candidature", "Bonjour", [])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        sender = GmailSender("rt-1", "cid", "csec", http=http)
        message_id = await sender.send(msg)
    assert message_id == "msg-42"
    # The payload is the RFC822 message, base64url-encoded in JSON {"raw": ...}
    import json
    raw = json.loads(seen["raw"])["raw"]
    decoded = base64.urlsafe_b64decode(raw + "==")
    assert b"To: hr@co.fr" in decoded


async def test_gmail_connect_requires_auth(client):
    r = await client.post("/api/account/gmail/connect", json={"code": "x", "redirect_uri": "http://localhost"})
    assert r.status_code in (401, 403)


async def test_gmail_connect_handles_non_json_google_error(client, monkeypatch):
    email, password = unique_email(), "password123"
    await client.post("/api/auth/register", json={"email": email, "password": password})

    real_post = httpx.AsyncClient.post

    class _BadResponse:
        # status 200 is deliberate: `resp.status_code != 200 or "refresh_token"
        # not in <parsed body>` short-circuits on a non-200 status without ever
        # calling .json(), so a 4xx/5xx stub can't exercise the parse-failure
        # path. Only a 200 with a malformed body forces the json() call that
        # used to raise uncaught.
        status_code = 200

        def json(self):
            raise ValueError("not json")

    async def fake_post(self, url, *args, **kwargs):
        # Only fake the Google token exchange; let the test client's own ASGI
        # calls (register above, the connect call below) go through for real.
        if str(url).startswith(TOKEN_URL):
            return _BadResponse()
        return await real_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    r = await client.post(
        "/api/account/gmail/connect", json={"code": "x", "redirect_uri": "http://localhost"}
    )
    assert r.status_code == 400
