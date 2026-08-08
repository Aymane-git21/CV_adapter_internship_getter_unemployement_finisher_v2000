"""Review-queue state machine. The audit trail is append-only; every
transition is recorded with a timestamp so 'what happened to this
application' is always answerable from the row alone."""
from datetime import UTC, datetime

TERMINAL: set[str] = {"replied", "rejected"}

ALLOWED: dict[str, set[str]] = {
    "inbox": {"generated", "rejected"},
    "generated": {"approved", "rejected"},
    "approved": {"sent", "rejected"},
    "sent": {"replied", "rejected"},
    "replied": set(),
    "rejected": set(),
}


def advance(application, to: str, note: str = "") -> None:
    """Move `application` to state `to`, or raise ValueError."""
    frm = application.status
    if to not in ALLOWED.get(frm, set()):
        raise ValueError(f"Illegal transition {frm} -> {to}")
    application.status = to
    entries = list(application.audit or [])
    entries.append(
        {"ts": datetime.now(UTC).isoformat(), "from": frm, "to": to, "note": note}
    )
    application.audit = entries
