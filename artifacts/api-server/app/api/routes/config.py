"""Panel configuration routes."""
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.bot_config import BotConfig
from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["config"])


def _serialize(config: BotConfig) -> dict:
    return {
        "bot_name": config.bot_name,
        "main_file": config.main_file,
        "auto_restart": config.auto_restart,
        "auto_install_deps": config.auto_install_deps,
        "max_log_lines": config.max_log_lines,
        "python_version": config.python_version,
    }


@router.get("")
async def get_config(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return the current panel configuration."""
    result = await db.execute(select(BotConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = BotConfig()
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return _serialize(config)


@router.put("")
async def update_config(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update panel configuration."""
    body = await request.json()

    result = await db.execute(select(BotConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = BotConfig()
        db.add(config)

    if "bot_name" in body:
        config.bot_name = body["bot_name"]
    if "main_file" in body:
        config.main_file = body["main_file"]
    if "auto_restart" in body:
        config.auto_restart = bool(body["auto_restart"])
    if "auto_install_deps" in body:
        config.auto_install_deps = bool(body["auto_install_deps"])
    if "max_log_lines" in body:
        config.max_log_lines = int(body["max_log_lines"])
    if "python_version" in body:
        config.python_version = body["python_version"]

    from datetime import datetime, timezone
    config.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(config)

    # Audit
    res2 = await db.execute(select(User).where(User.id == user_id))
    user = res2.scalar_one_or_none()
    db.add(AuditLog(
        user_id=user_id,
        username=user.username if user else None,
        action="config_update",
        details="Panel configuration updated",
    ))
    await db.commit()

    return _serialize(config)
