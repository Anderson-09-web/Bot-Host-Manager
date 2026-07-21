"""Per-guild bot configuration stored in PostgreSQL."""
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class BotData(Base):
    """Key-value store for bot guild configurations.

    Each row is one setting for one Discord guild.  The composite unique
    constraint on (guild_id, key) lets us upsert individual keys without
    touching the rest of a guild's config.
    """

    __tablename__ = "bot_data"
    __table_args__ = (
        UniqueConstraint("guild_id", "key", name="uq_bot_data_guild_key"),
        Index("ix_bot_data_guild_id", "guild_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    # JSON column — stores str, int, bool, list, dict, or None
    value: Mapped[object] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
