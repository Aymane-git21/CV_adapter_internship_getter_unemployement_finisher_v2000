"""MIME correctness, header-injection rejection, .eml fallback."""
from pathlib import Path

import pytest

from backend.app.mailer import EmlSender, build_application_email, write_eml

PDF = b"%PDF-1.4 fake"


def _msg():
    return build_application_email(
        sender="alex@example.com",
        to="recrutement@lumina.example",
        subject="Candidature — Ingénieur ML (185XKPT)",
        body="Bonjour,\n\nVeuillez trouver ma candidature ci-jointe.\n\nAlex",
        attachments=[("CV_Alex_Martin.pdf", PDF), ("Lettre_Alex_Martin.pdf", PDF)],
    )


def test_mime_structure():
    msg = _msg()
    assert msg["To"] == "recrutement@lumina.example"
    assert "Candidature" in msg["Subject"]
    parts = list(msg.iter_attachments())
    assert [p.get_filename() for p in parts] == ["CV_Alex_Martin.pdf", "Lettre_Alex_Martin.pdf"]
    assert all(p.get_content_type() == "application/pdf" for p in parts)
    assert "Veuillez trouver" in msg.get_body(("plain",)).get_content()


@pytest.mark.parametrize("field", ["to", "subject", "sender"])
def test_header_injection_rejected(field):
    kwargs = dict(sender="a@b.c", to="x@y.z", subject="Hi", body="B", attachments=[])
    kwargs[field] = "evil\r\nBcc: spam@spam.spam"
    with pytest.raises(ValueError):
        build_application_email(**kwargs)


def test_attachment_filename_injection_rejected():
    with pytest.raises(ValueError):
        build_application_email(
            sender="a@b.c", to="x@y.z", subject="Hi", body="B",
            attachments=[("evil.pdf\r\nBcc: spam@spam.spam", PDF)],
        )


async def test_eml_sender_writes_file(tmp_path: Path):
    path_str = await EmlSender(tmp_path).send(_msg())
    p = Path(path_str)
    assert p.exists() and p.suffix == ".eml"
    content = p.read_bytes()
    assert b"recrutement@lumina.example" in content and b"application/pdf" in content


def test_write_eml_unique_names(tmp_path: Path):
    a = write_eml(_msg(), tmp_path)
    b = write_eml(_msg(), tmp_path)
    assert a != b
