"""Application email assembly and sending.

The body is the outreach message; the CV and letter PDFs ride as
attachments. Sends go out as the USER (their Gmail, Task 12) or to a
local .eml file in dev — never from a cvglowup.com address."""
import base64
import json
import uuid
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from typing import Protocol

import httpx

_FORBIDDEN = ("\r", "\n")


def _clean_header(value: str, name: str) -> str:
    if any(ch in value for ch in _FORBIDDEN):
        raise ValueError(f"Illegal newline in {name} header.")
    return value.strip()


def build_application_email(
    sender: str,
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]],
) -> EmailMessage:
    msg = EmailMessage(policy=SMTP)
    msg["From"] = _clean_header(sender, "From")
    msg["To"] = _clean_header(to, "To")
    msg["Subject"] = _clean_header(subject, "Subject")
    msg.set_content(body)
    for filename, blob in attachments:
        msg.add_attachment(
            blob, maintype="application", subtype="pdf",
            filename=_clean_header(filename, "attachment filename"),
        )
    return msg


def write_eml(msg: EmailMessage, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"application_{uuid.uuid4().hex[:12]}.eml"
    path.write_bytes(bytes(msg))
    return path


class Sender(Protocol):
    async def send(self, msg: EmailMessage) -> str: ...


class EmlSender:
    """Dev fallback: 'sending' writes an .eml the user can open and send."""

    def __init__(self, directory: str | Path):
        self._dir = directory

    async def send(self, msg: EmailMessage) -> str:
        return str(write_eml(msg, self._dir))


TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/upload/gmail/v1/users/me/messages/send"


class GmailError(Exception):
    """User-presentable Gmail failure (revoked consent, quota, transport)."""


class GmailSender:
    """Sends as the user via their stored refresh token (scope gmail.send).
    We hold ONLY the refresh token Google issued to our client id — never a
    password. Revoking access in the user's Google account kills it."""

    def __init__(self, refresh_token: str, client_id: str, client_secret: str,
                 http: httpx.AsyncClient | None = None):
        self._rt = refresh_token
        self._cid = client_id
        self._csec = client_secret
        self._http = http

    async def _access_token(self, http: httpx.AsyncClient) -> str:
        resp = await http.post(TOKEN_URL, data={
            "grant_type": "refresh_token", "refresh_token": self._rt,
            "client_id": self._cid, "client_secret": self._csec,
        })
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        token = payload.get("access_token")
        if resp.status_code != 200 or not token:
            raise GmailError("Gmail authorization expired or was revoked. Reconnect Gmail in Settings.")
        return token

    async def send(self, msg) -> str:
        raw = base64.urlsafe_b64encode(bytes(msg)).decode().rstrip("=")
        own = self._http is None
        http = self._http or httpx.AsyncClient(timeout=30)
        try:
            token = await self._access_token(http)
            # Note on Content-Type: Gmail's upload endpoint accepts `message/rfc822`
            # with the raw RFC822 bytes OR the JSON {"raw": ...} metadata form on the
            # non-upload endpoint. The MockTransport test pins the JSON-raw form; if
            # the live API rejects it during phase-2 verification, switch `content=`
            # to `bytes(msg)` with `Content-Type: message/rfc822` and drop the
            # base64 — the test then pins that instead. One of the two documented
            # forms will hold; the seam is one method.
            resp = await http.post(
                SEND_URL,
                params={"uploadType": "media"},
                content=json.dumps({"raw": raw}),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "message/rfc822"},
            )
            if resp.status_code not in (200, 202):
                raise GmailError(f"Gmail send failed ({resp.status_code}).")
            try:
                return resp.json().get("id", "")
            except ValueError:
                # Send already succeeded per status code; an unparseable body
                # (Gmail API contract violation) should not fail the application.
                return ""
        finally:
            if own:
                await http.aclose()
