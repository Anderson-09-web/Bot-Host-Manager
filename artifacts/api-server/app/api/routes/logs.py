"""Bot log management routes."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.log_entry import LogEntry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def get_logs(
    limit: int = Query(default=200, ge=1, le=5000),
    level: Optional[str] = Query(default=None),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return stored bot log entries, newest first."""
    q = select(LogEntry).order_by(desc(LogEntry.timestamp))
    if level:
        q = q.where(LogEntry.level == level.upper())
    q = q.limit(limit)
    result = await db.execute(q)
    entries = result.scalars().all()

    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "level": e.level,
            "message": e.message,
            "source": e.source,
        }
        for e in entries
    ]


@router.delete("")
async def clear_logs(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete all log entries from the database."""
    await db.execute(delete(LogEntry))
    await db.commit()
    return {"success": True, "message": "All logs cleared"}
