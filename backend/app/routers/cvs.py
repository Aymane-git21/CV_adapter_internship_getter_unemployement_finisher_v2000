"""Master CV management: paste text, upload PDF (parsed by the AI), edit data."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai import get_provider
from ..ai.base import AIError
from ..config import get_settings
from ..db import get_db
from ..models import MasterCV, Photo, User
from ..schemas import CVData, MasterCVIn
from ..security import get_byok_key, get_current_user, require_user

router = APIRouter(prefix="/api", tags=["cvs"])

_MAX_PDF = 8 * 1024 * 1024
_MAX_PHOTO = 3 * 1024 * 1024
_MAX_NAME = 120  # MasterCV.name is String(120); Postgres raises on overflow, SQLite doesn't


def _clamp_name(name: str | None) -> str:
    return (name or "").strip()[:_MAX_NAME] or "My CV"


def _cv_payload(cv: MasterCV) -> dict:
    return {
        "id": cv.id,
        "name": cv.name,
        "is_default": cv.is_default,
        "data": cv.data,
        "has_raw_text": bool(cv.raw_text),
        "updated_at": cv.updated_at.isoformat() if cv.updated_at else None,
    }


@router.get("/cvs")
async def list_cvs(
    user: Annotated[User, Depends(require_user)], db: Annotated[AsyncSession, Depends(get_db)]
):
    rows = (
        (await db.execute(select(MasterCV).where(MasterCV.user_id == user.id).order_by(MasterCV.id)))
        .scalars().all()
    )
    return [_cv_payload(c) for c in rows]


@router.post("/cvs")
async def create_cv(
    body: MasterCVIn,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    byok: Annotated[str | None, Depends(get_byok_key)],
):
    data = body.data
    if data is None and body.raw_text:
        try:
            data = await get_provider(byok).parse_cv(body.raw_text, None, user.language)
        except AIError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    if data is None:
        raise HTTPException(status_code=422, detail="Provide raw_text or structured data.")
    count = len((await db.execute(select(MasterCV.id).where(MasterCV.user_id == user.id))).all())
    cv = MasterCV(
        user_id=user.id, name=_clamp_name(body.name), data=data.model_dump(),
        raw_text=body.raw_text, is_default=count == 0,
    )
    db.add(cv)
    await db.commit()
    await db.refresh(cv)
    return _cv_payload(cv)


@router.post("/cvs/upload")
async def upload_cv(
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    byok: Annotated[str | None, Depends(get_byok_key)],
    file: UploadFile = File(...),
    name: str = Form("My CV"),
):
    content = await file.read()
    if len(content) > _MAX_PDF:
        raise HTTPException(status_code=413, detail="PDF too large (8 MB max).")
    # The PDF spec allows the %PDF header anywhere in the first 1024 bytes;
    # some generators prepend junk, so don't require it at offset 0.
    if b"%PDF" not in content[:1024]:
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")
    if not get_settings().ai_enabled and not byok:
        raise HTTPException(
            status_code=422,
            detail="PDF parsing needs the AI service. Paste your CV as text instead (offline mode).",
        )
    try:
        data = await get_provider(byok).parse_cv(None, content, user.language)
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    count = len((await db.execute(select(MasterCV.id).where(MasterCV.user_id == user.id))).all())
    cv = MasterCV(user_id=user.id, name=_clamp_name(name), data=data.model_dump(), is_default=count == 0)
    db.add(cv)
    await db.commit()
    await db.refresh(cv)
    return _cv_payload(cv)


@router.put("/cvs/{cv_id}")
async def update_cv(
    cv_id: int,
    body: MasterCVIn,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cv = await db.get(MasterCV, cv_id)
    if cv is None or cv.user_id != user.id:
        raise HTTPException(status_code=404, detail="CV not found.")
    if body.name:
        cv.name = body.name
    if body.data is not None:
        cv.data = CVData.model_validate(body.data.model_dump()).model_dump()
    if body.raw_text is not None:
        cv.raw_text = body.raw_text
    await db.commit()
    await db.refresh(cv)
    return _cv_payload(cv)


@router.post("/cvs/{cv_id}/default")
async def set_default(
    cv_id: int,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cv = await db.get(MasterCV, cv_id)
    if cv is None or cv.user_id != user.id:
        raise HTTPException(status_code=404, detail="CV not found.")
    await db.execute(update(MasterCV).where(MasterCV.user_id == user.id).values(is_default=False))
    cv.is_default = True
    await db.commit()
    return {"ok": True}


@router.delete("/cvs/{cv_id}")
async def delete_cv(
    cv_id: int,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cv = await db.get(MasterCV, cv_id)
    if cv is None or cv.user_id != user.id:
        raise HTTPException(status_code=404, detail="CV not found.")
    await db.delete(cv)
    await db.commit()
    return {"ok": True}


# ---- Photos -----------------------------------------------------------------

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG"


@router.post("/photos")
async def upload_photo(
    db: Annotated[AsyncSession, Depends(get_db)],
    # Guests generate documents too, so photos are anonymous-friendly by design
    # (user_id is nullable). require_user here would 401 every guest upload.
    user: Annotated[User | None, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    content = await file.read()
    if len(content) > _MAX_PHOTO:
        raise HTTPException(status_code=413, detail="Photo too large (3 MB max).")
    if content.startswith(_JPEG_MAGIC):
        mime = "image/jpeg"
    elif content.startswith(_PNG_MAGIC):
        mime = "image/png"
    else:
        raise HTTPException(status_code=415, detail="JPEG or PNG only.")
    photo = Photo(id=uuid.uuid4().hex, user_id=user.id if user else None, content=content, mime=mime)
    db.add(photo)
    await db.commit()
    return {"id": photo.id}


@router.get("/photos/{photo_id}")
async def get_photo(
    photo_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from fastapi.responses import Response as RawResponse

    photo = await db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found.")
    return RawResponse(content=photo.content, media_type=photo.mime)
