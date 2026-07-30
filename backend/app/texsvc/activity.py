"""Last-LaTeX-compile bookkeeping for the idle reaper. Caller commits."""
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import LatexActivity


async def touch_latex_activity(db: AsyncSession) -> None:
    row = await db.get(LatexActivity, 1)
    if row is None:
        db.add(LatexActivity(id=1, last_compile_at=datetime.now(UTC)))
    else:
        row.last_compile_at = datetime.now(UTC)
