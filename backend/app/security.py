"""Password hashing, session cookies, and auth dependencies.

Password hashes use the exact werkzeug format ("pbkdf2:sha256:<iter>$salt$hex")
so accounts created by the legacy Flask app keep working after migration —
without depending on werkzeug itself.
"""
import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_db
from .models import User

SESSION_COOKIE = "cvg_session"
SESSION_MAX_AGE = 30 * 24 * 3600
_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"pbkdf2:sha256:{_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        method, salt, hexdigest = stored.split("$", 2)
        if not method.startswith("pbkdf2:"):
            return False  # unknown scheme (e.g. scrypt) — fail closed
        parts = method.split(":")
        algo = parts[1]
        iterations = int(parts[2]) if len(parts) > 2 else 260_000
        digest = hashlib.pbkdf2_hmac(algo, password.encode(), salt.encode(), iterations)
        return hmac.compare_digest(digest.hex(), hexdigest)
    except (ValueError, IndexError):
        return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="cvg-session")


def set_session(response: Response, user_id: int) -> None:
    token = _serializer().dumps({"uid": user_id})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=get_settings().is_prod,
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def read_session(request: Request) -> int | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=SESSION_MAX_AGE)
        return int(payload["uid"])
    except (BadSignature, KeyError, ValueError, TypeError):
        return None


async def get_current_user(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> User | None:
    uid = read_session(request)
    if uid is None:
        return None
    return await db.get(User, uid)


async def require_user(user: Annotated[User | None, Depends(get_current_user)]) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def get_byok_key(x_user_gemini_key: Annotated[str | None, Header()] = None) -> str | None:
    """User-supplied Gemini key: used transiently for this request, never stored."""
    key = (x_user_gemini_key or "").strip()
    return key or None


def guest_key_hash(request: Request) -> str:
    """Salted hash identifying an anonymous visitor (IP-based, not stored raw)."""
    ip = request.client.host if request.client else "unknown"
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip()
    return hashlib.sha256(f"{ip}|{get_settings().secret_key}".encode()).hexdigest()
