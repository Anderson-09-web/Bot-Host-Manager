"""Bot and panel configuration model."""
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class BotConfig(Base):
    __tablename__ = "bot_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_name: Mapped[str] = mapped_column(String(255), default="My Discord Bot", nullable=False)
    main_file: Mapped[str] = mapped_column(String(255), default="main.py", nullable=False)
    auto_restart: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_install_deps: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_log_lines: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    python_version: Mapped[str] = mapped_column(String(20), default="3.13", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
