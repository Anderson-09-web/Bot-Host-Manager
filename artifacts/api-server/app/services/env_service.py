"""Service for managing environment variables stored in the database."""
import logging
from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.env_var import EnvVar

logger = logging.getLogger(__name__)


class EnvService:
    """In-memory + database env var service. Used by bot manager to inject env vars."""

    async def get_all(self, db: Optional[AsyncSession] = None) -> List[dict]:
        """Return all env vars as list of dicts."""
        from app.core.database import AsyncSessionLocal
        ctx = db or AsyncSessionLocal()
        try:
            result = await ctx.execute(select(EnvVar).order_by(EnvVar.key))
            vars = result.scalars().all()
            return [{"key": v.key, "value": v.value, "is_secret": v.is_secret} for v in vars]
        finally:
            if not db:
                await ctx.close()


# Singleton
env_service = EnvService()
