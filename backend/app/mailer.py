"""Application email assembly and sending.

The body is the outreach message; the CV and letter PDFs ride as
attachments. Sends go out as the USER (their Gmail, Task 12) or to a
local .eml file in dev — never from a cvglowup.com address."""
import uuid
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from typing import Protocol

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
            blob, maintype="application", subtype="pdf", filename=filename
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
