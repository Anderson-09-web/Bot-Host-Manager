"""Audit log routes."""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=500),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return recent audit log entries."""
    result = await db.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    )
    entries = result.scalars().all()
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "username": e.username,
            "action": e.action,
            "details": e.details,
            "ip_address": e.ip_address,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]
