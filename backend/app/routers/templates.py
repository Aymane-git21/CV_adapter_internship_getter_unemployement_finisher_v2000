"""Read-only Typst template source for the studio's code viewer.

The source editor makes `#import "/typst/<name>.typ"` lines clickable; this
endpoint serves exactly those files. The name regex is the whole security
story: lowercase snake names, no dots beyond the suffix, no separators, so
traversal cannot be expressed. Template code is repo-public, no auth needed.
"""
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from ..config import get_settings

router = APIRouter(prefix="/api/templates", tags=["templates"])

_NAME = re.compile(r"^[a-z0-9_]{1,32}\.typ$")


@router.get("/typst/{name}", response_class=PlainTextResponse)
async def template_source(name: str) -> str:
    if not _NAME.match(name):
        raise HTTPException(status_code=422, detail="Invalid template name.")
    path = get_settings().templates_dir / "typst" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Unknown template.")
    return path.read_text(encoding="utf-8")
