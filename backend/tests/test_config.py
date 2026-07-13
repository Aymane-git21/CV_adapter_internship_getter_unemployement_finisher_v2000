"""Regression tests for Settings.sqlalchemy_url URL translation.

The async driver (asyncpg) does not understand libpq's `sslmode=` query param or
Neon's `channel_binding=`. A prior bug rewrote `sslmode=require` to `ssl=true`,
which asyncpg rejects ("`sslmode` parameter must be one of: ... require ...") and
crashed startup on Postgres. These lock the translation down.
"""
import pytest

from backend.app.config import Settings


def _url(database_url: str) -> str:
    return Settings(database_url=database_url).sqlalchemy_url


@pytest.mark.parametrize(
    "raw, expected",
    [
        # sqlite passes through untouched
        (
            "sqlite+aiosqlite:///x.db",
            "sqlite+aiosqlite:///x.db",
        ),
        # bare postgres gets the async driver, nothing else
        (
            "postgresql://u:p@h/db",
            "postgresql+asyncpg://u:p@h/db",
        ),
        # heroku-style short scheme is upgraded too
        (
            "postgres://u:p@h/db",
            "postgresql+asyncpg://u:p@h/db",
        ),
        # the bug: sslmode must become ssl=<same value>, never ssl=true
        (
            "postgresql://u:p@h/db?sslmode=require",
            "postgresql+asyncpg://u:p@h/db?ssl=require",
        ),
        # Neon's default: sslmode first, channel_binding stripped
        (
            "postgresql://u:p@h/db?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@h/db?ssl=require",
        ),
        # reversed order: channel_binding stripped, leading separator repaired
        (
            "postgres://u:p@h/db?channel_binding=require&sslmode=require",
            "postgresql+asyncpg://u:p@h/db?ssl=require",
        ),
        # non-require ssl modes keep their value name
        (
            "postgresql://u:p@h/db?sslmode=verify-full",
            "postgresql+asyncpg://u:p@h/db?ssl=verify-full",
        ),
    ],
)
def test_sqlalchemy_url_translation(raw, expected):
    assert _url(raw) == expected


def test_ssl_true_never_emitted():
    """asyncpg rejects ssl=true; it must never appear in the rendered URL."""
    out = _url("postgresql://u:p@h/db?sslmode=require&channel_binding=require")
    assert "ssl=true" not in out
    assert "sslmode=" not in out
    assert "channel_binding" not in out


def test_ai_enabled_via_vertex_without_key():
    """GEMINI_USE_VERTEX=1 turns the AI on with no API key (service-account
    auth); CVG_FAKE_AI still forces the offline provider."""
    assert Settings(gemini_api_key="", gemini_use_vertex=True, cvg_fake_ai=False).ai_enabled
    assert not Settings(gemini_api_key="", gemini_use_vertex=False, cvg_fake_ai=False).ai_enabled
    assert not Settings(gemini_api_key="", gemini_use_vertex=True, cvg_fake_ai=True).ai_enabled
