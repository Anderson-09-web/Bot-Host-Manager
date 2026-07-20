"""Bot management routes: start, stop, restart, kill, status."""
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.audit_log import AuditLog
from app.models.bot_config import BotConfig
from app.models.user import User
from app.services.bot_manager import bot_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bot", tags=["bot"])


async def _get_config(db: AsyncSession) -> BotConfig | None:
    result = await db.execute(select(BotConfig).limit(1))
    return result.scalar_one_or_none()


async def _audit(db: AsyncSession, user_id: int, action: str, details: str, ip: str):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    db.add(AuditLog(
        user_id=user_id,
        username=user.username if user else None,
        action=action,
        details=details,
        ip_address=ip,
    ))
    await db.commit()


@router.get("/status")
async def get_bot_status(user_id: int = Depends(get_current_user_id)):
    """Return current bot status, PID, uptime, and framework."""
    return bot_manager.get_status_dict()


@router.post("/start")
async def start_bot(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Start the Discord bot."""
    config = await _get_config(db)
    main_file = config.main_file if config else "main.py"
    auto_install = config.auto_install_deps if config else True

    ip = request.client.host if request.client else "unknown"
    await _audit(db, user_id, "bot_start", f"Start requested (main: {main_file})", ip)

    # Start in background so we return immediately
    import asyncio
    asyncio.create_task(bot_manager.start(main_file=main_file, auto_install=auto_install))

    return bot_manager.get_status_dict()


@router.post("/stop")
async def stop_bot(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Gracefully stop the Discord bot."""
    ip = request.client.host if request.client else "unknown"
    await _audit(db, user_id, "bot_stop", "Stop requested", ip)

    import asyncio
    asyncio.create_task(bot_manager.stop())

    return bot_manager.get_status_dict()


@router.post("/restart")
async def restart_bot(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Restart the Discord bot."""
    config = await _get_config(db)
    main_file = config.main_file if config else "main.py"

    ip = request.client.host if request.client else "unknown"
    await _audit(db, user_id, "bot_restart", f"Restart requested (main: {main_file})", ip)

    import asyncio
    asyncio.create_task(bot_manager.restart(main_file=main_file))

    return bot_manager.get_status_dict()


@router.post("/kill")
async def kill_bot(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Force kill the Discord bot process."""
    ip = request.client.host if request.client else "unknown"
    await _audit(db, user_id, "bot_kill", "Force kill requested", ip)

    import asyncio
    asyncio.create_task(bot_manager.kill())

    return bot_manager.get_status_dict()
