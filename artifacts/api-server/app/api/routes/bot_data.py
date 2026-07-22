"""Internal bot-data API — key/value config store for Discord guilds.

This endpoint is called exclusively by the bot subprocess via config_manager.py.
Auth uses a HMAC-derived key injected as PANEL_BOT_KEY into the bot's environment,
so no panel user JWT is required and no credentials are ever written to disk.
"""
import hashlib
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.bot_data import BotData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bot-data", tags=["bot-data"])


# ── Auth ─────────────────────────────────────────────────────────────────────

def _expected_key() -> str:
    """Derive the bot API key from the JWT secret (stable, no storage needed)."""
    return hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        b"bot-api-v1",
        hashlib.sha256,
    ).hexdigest()


async def verify_bot_key(authorization: str = Header(default="")):
    """FastAPI dependency: verify the bot's bearer token."""
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Missing bot API key")
    token = authorization[len(prefix):]
    expected = _expected_key()
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Invalid bot API key")
    return True


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _rows_to_dict(rows: list[BotData]) -> dict:
    """Convert a list of BotData rows to {guild_id: {key: value}} mapping."""
    result: dict[str, dict] = {}
    for row in rows:
        result.setdefault(row.guild_id, {})[row.key] = row.value
    return result


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def get_all(
    _: bool = Depends(verify_bot_key),
    db: AsyncSession = Depends(get_db),
):
    """Return all guild configs as {guild_id: {key: value}}."""
    result = await db.execute(select(BotData).order_by(BotData.guild_id, BotData.key))
    rows = result.scalars().all()
    return _rows_to_dict(rows)


@router.put("/{guild_id}/{key}")
async def upsert_key(
    guild_id: str,
    key: str,
    request: Request,
    _: bool = Depends(verify_bot_key),
    db: AsyncSession = Depends(get_db),
):
    """Upsert a single setting for a guild."""
    body = await request.json()
    value = body.get("value")

    stmt = (
        pg_insert(BotData)
        .values(
            guild_id=guild_id,
            key=key,
            value=value,
            updated_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_bot_data_guild_key",
            set_={"value": value, "updated_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()
    return {"guild_id": guild_id, "key": key, "value": value}


@router.delete("/{guild_id}/{key}")
async def delete_key(
    guild_id: str,
    key: str,
    _: bool = Depends(verify_bot_key),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single setting key for a guild."""
    await db.execute(
        delete(BotData).where(BotData.guild_id == guild_id, BotData.key == key)
    )
    await db.commit()
    return {"deleted": True, "guild_id": guild_id, "key": key}


@router.delete("/{guild_id}")
async def clear_guild(
    guild_id: str,
    module: str | None = None,
    _: bool = Depends(verify_bot_key),
    db: AsyncSession = Depends(get_db),
):
    """Delete settings for a guild.

    If *module* query-param is supplied, only keys that start with
    ``{module}/`` are removed (scoped cog cleanup).  Otherwise ALL
    keys for the guild are deleted.
    """
    if module:
        prefix = f"{module}/"
        stmt = delete(BotData).where(
            BotData.guild_id == guild_id,
            BotData.key.like(f"{prefix}%"),
        )
    else:
        stmt = delete(BotData).where(BotData.guild_id == guild_id)
    result = await db.execute(stmt)
    await db.commit()
    return {"deleted": True, "guild_id": guild_id, "module": module, "rows": result.rowcount}


@router.delete("/module/{module_name}")
async def clear_module(
    module_name: str,
    _: bool = Depends(verify_bot_key),
    db: AsyncSession = Depends(get_db),
):
    """Delete ALL bot_data entries across ALL guilds whose key starts with
    ``{module_name}/``.

    Called internally when a cog .py file is deleted so that stale configs
    don't bleed into a newly-uploaded cog with the same name.
    """
    prefix = f"{module_name}/"
    result = await db.execute(
        delete(BotData).where(BotData.key.like(f"{prefix}%"))
    )
    await db.commit()
    return {"deleted": True, "module": module_name, "rows": result.rowcount}
