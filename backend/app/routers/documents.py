"""Document editing: structured updates, raw-source compiles, chat edits, PDF."""
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai import get_provider
from ..ai.base import AIError
from ..db import get_db
from ..models import Document, Photo, User
from ..schemas import ChatIn, CompileIn, CVData, DocumentUpdateIn, LetterData
from ..security import get_byok_key, get_current_user
from ..typstsvc import renderer

router = APIRouter(prefix="/api/documents", tags=["documents"])

_MAX_SOURCE = 200_000


async def _get_doc(db: AsyncSession, doc_id: str, user: User | None) -> Document:
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    # Owned documents require the owner; guest documents are capability-style
    # (the random id is the secret).
    if doc.user_id is not None and (user is None or user.id != doc.user_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


async def _photo_bytes(db: AsyncSession, doc: Document) -> bytes | None:
    if not doc.photo_id or not (doc.settings or {}).get("show_photo"):
        return None
    photo = await db.get(Photo, doc.photo_id)
    return photo.content if photo else None


def _doc_payload(doc: Document, svgs: list[str] | None = None) -> dict:
    return {
        "id": doc.id,
        "job_id": doc.job_id,
        "kind": doc.kind,
        "title": doc.title,
        "template": doc.template_id,
        "settings": doc.settings,
        "data": doc.data,
        "source": doc.source,
        "mode": doc.mode,
        "text_content": doc.text_content,
        "photo_id": doc.photo_id,
        "score_before": doc.score_before,
        "score_after": doc.score_after,
        "keywords": doc.keywords,
        "svgs": svgs,
    }


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(get_current_user)],
    include_svg: bool = True,
):
    doc = await _get_doc(db, doc_id, user)
    svgs = None
    if include_svg and doc.kind != "message" and doc.source:
        result = await renderer.compile_source(doc.source, photo=await _photo_bytes(db, doc), fmt="svg")
        if result.ok:
            svgs = result.svgs
    return _doc_payload(doc, svgs)


@router.put("/{doc_id}")
async def update_document(
    doc_id: str,
    body: DocumentUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(get_current_user)],
):
    doc = await _get_doc(db, doc_id, user)

    if doc.kind == "message":
        if body.text_content is not None:
            doc.text_content = body.text_content[:5000]
        await db.commit()
        return _doc_payload(doc)

    if body.data is not None:
        schema = CVData if doc.kind == "cv" else LetterData
        doc.data = schema.model_validate(body.data).model_dump()
        doc.mode = "data"
    if body.settings is not None:
        new_settings = body.settings.model_dump()
        doc.template_id = new_settings.get("template", doc.template_id)
        doc.settings = new_settings

    photo = await _photo_bytes(db, doc)
    if doc.mode == "data":
        result, source = await renderer.compile_document(
            doc.kind, doc.template_id, doc.data or {}, doc.settings or {}, photo=photo, fmt="svg"
        )
        if not result.ok:
            raise HTTPException(status_code=422, detail={"diagnostics": result.diagnostics})
        doc.source = source
        doc.settings = {**(doc.settings or {}), "density": result.density_used}
    else:
        result = await renderer.compile_source(doc.source or "", photo=photo, fmt="svg")
        if not result.ok:
            raise HTTPException(status_code=422, detail={"diagnostics": result.diagnostics})
    doc.pdf = None  # invalidate cache
    await db.commit()
    return _doc_payload(doc, result.svgs)


@router.post("/{doc_id}/compile")
async def compile_document(
    doc_id: str,
    body: CompileIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(get_current_user)],
):
    """Compile preview. With a source body, validates + saves it (source mode)."""
    doc = await _get_doc(db, doc_id, user)
    if doc.kind == "message":
        raise HTTPException(status_code=422, detail="Messages are plain text.")

    source = body.source if body.source is not None else (doc.source or "")
    if len(source) > _MAX_SOURCE:
        raise HTTPException(status_code=413, detail="Source too large.")
    if re.search(r"^\s*#?import\s+\"(?!/typst/)", source, re.M):
        raise HTTPException(status_code=422, detail="Imports outside /typst/ are not allowed.")

    result = await renderer.compile_source(source, photo=await _photo_bytes(db, doc), fmt="svg")
    saved = False
    if body.source is not None and result.ok:
        doc.source = body.source
        doc.mode = "source"
        doc.pdf = None
        await db.commit()
        saved = True
    return {
        "ok": result.ok,
        "pages": result.pages,
        "svgs": result.svgs,
        "diagnostics": result.diagnostics,
        "saved": saved,
        "mode": doc.mode,
    }


@router.post("/{doc_id}/chat")
async def chat_edit(
    doc_id: str,
    body: ChatIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(get_current_user)],
    byok: Annotated[str | None, Depends(get_byok_key)],
):
    doc = await _get_doc(db, doc_id, user)
    provider = get_provider(byok)
    lang = (doc.settings or {}).get("lang", "en")

    try:
        if doc.kind == "message":
            new_text = await provider.edit_source(doc.text_content or "", body.message)
            doc.text_content = new_text.replace("// edit requested:", "").strip()[:5000]
            await db.commit()
            return {"ok": True, "text_content": doc.text_content, "reply": "Done — message updated."}

        photo = await _photo_bytes(db, doc)
        if doc.mode == "data":
            schema = CVData if doc.kind == "cv" else LetterData
            current = schema.model_validate(doc.data or {})
            if doc.kind == "cv":
                edited = await provider.edit_cv_data(current, body.message, lang)
            else:
                edited = await provider.edit_letter_data(current, body.message, lang)
            doc.data = edited.model_dump()
            result, source = await renderer.compile_document(
                doc.kind, doc.template_id, doc.data, doc.settings or {}, photo=photo, fmt="svg"
            )
            if not result.ok:
                raise HTTPException(status_code=422, detail={"diagnostics": result.diagnostics})
            doc.source = source
        else:
            new_source = await provider.edit_source(doc.source or "", body.message)
            result = await renderer.compile_source(new_source, photo=photo, fmt="svg")
            if not result.ok:
                return {
                    "ok": False,
                    "reply": "The edit produced source that does not compile — I did not apply it.",
                    "diagnostics": result.diagnostics,
                }
            doc.source = new_source
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    doc.pdf = None
    await db.commit()
    return {
        "ok": True,
        "reply": "Done — document updated.",
        "data": doc.data,
        "source": doc.source,
        "svgs": result.svgs,
        "mode": doc.mode,
    }


@router.get("/{doc_id}/pdf")
async def download_pdf(
    doc_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(get_current_user)],
):
    doc = await _get_doc(db, doc_id, user)
    if doc.kind == "message":
        raise HTTPException(status_code=422, detail="Messages are plain text — use copy instead.")
    if doc.pdf is None:
        result = await renderer.compile_source(
            doc.source or "", photo=await _photo_bytes(db, doc), fmt="pdf"
        )
        if not result.ok:
            raise HTTPException(status_code=422, detail={"diagnostics": result.diagnostics})
        doc.pdf = result.pdf
        await db.commit()
    safe_title = re.sub(r"[^\w\- ]+", "", doc.title or "document").strip()[:60] or "document"
    prefix = "CV" if doc.kind == "cv" else "CoverLetter"
    return Response(
        content=doc.pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{prefix} - {safe_title}.pdf"'},
    )


@router.get("/{doc_id}/source.typ")
async def download_source(
    doc_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User | None, Depends(get_current_user)],
):
    doc = await _get_doc(db, doc_id, user)
    if not doc.source:
        raise HTTPException(status_code=404, detail="No source available.")
    return Response(
        content=doc.source,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{doc.kind}-{doc.id[:8]}.typ"'},
    )
