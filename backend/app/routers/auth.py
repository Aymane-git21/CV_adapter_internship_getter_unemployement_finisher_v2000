"""Email/password and Google sign-in."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import User
from ..quota import quota_snapshot
from ..schemas import GoogleLoginIn, LoginIn, RegisterIn
from ..security import clear_session, get_current_user, hash_password, set_session, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "plan": user.plan,
        "language": user.language,
        "quota": quota_snapshot(user),
    }


@router.post("/register")
async def register(body: RegisterIn, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    email = body.email.lower().strip()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    set_session(response, user.id)
    return _user_payload(user)


@router.post("/login")
async def login(body: LoginIn, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    email = body.email.lower().strip()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    set_session(response, user.id)
    return _user_payload(user)


@router.post("/google")
async def google_login(
    body: GoogleLoginIn, response: Response, db: Annotated[AsyncSession, Depends(get_db)]
):
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google sign-in is not configured.")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        info = id_token.verify_oauth2_token(
            body.credential, google_requests.Request(), settings.google_client_id
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Google token could not be verified.") from exc

    sub = info["sub"]
    email = (info.get("email") or "").lower()
    user = (await db.execute(select(User).where(User.google_sub == sub))).scalar_one_or_none()
    if user is None and email:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is not None:
            user.google_sub = sub
    if user is None:
        user = User(email=email or f"google-{sub}@users.cvglowup.com", google_sub=sub)
        db.add(user)
    await db.commit()
    await db.refresh(user)
    set_session(response, user.id)
    return _user_payload(user)


@router.post("/logout")
async def logout(response: Response):
    clear_session(response)
    return {"ok": True}


@router.get("/me")
async def me(user: Annotated[User | None, Depends(get_current_user)]):
    if user is None:
        return {"authenticated": False, "quota": quota_snapshot(None)}
    return {"authenticated": True, **_user_payload(user)}
