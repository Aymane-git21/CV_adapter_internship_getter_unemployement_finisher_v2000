"""Review-queue state machine: inbox → generated → approved → sent → replied|rejected."""
import pytest

from backend.app.pipeline_states import ALLOWED, TERMINAL, advance


class FakeApp:
    def __init__(self, status="inbox"):
        self.status = status
        self.audit = []


def test_happy_path():
    a = FakeApp()
    for to in ("generated", "approved", "sent", "replied"):
        advance(a, to)
    assert a.status == "replied"
    assert [e["to"] for e in a.audit] == ["generated", "approved", "sent", "replied"]
    assert all("ts" in e and "from" in e for e in a.audit)


def test_reject_allowed_from_any_non_terminal():
    for start in ("inbox", "generated", "approved", "sent"):
        a = FakeApp(start)
        advance(a, "rejected", note="not a fit")
        assert a.status == "rejected"
        assert a.audit[-1]["note"] == "not a fit"


def test_illegal_transitions_raise():
    with pytest.raises(ValueError):
        advance(FakeApp("inbox"), "sent")
    with pytest.raises(ValueError):
        advance(FakeApp("sent"), "approved")
    with pytest.raises(ValueError):
        advance(FakeApp("replied"), "rejected")  # terminal


def test_terminal_set():
    assert TERMINAL == {"replied", "rejected"}
    assert set(ALLOWED) == {"inbox", "generated", "approved", "sent", "replied", "rejected"}
