"""Async SQLAlchemy database setup for Neon PostgreSQL."""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# Create async engine with connection pool settings optimized for Neon
engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={
        "ssl": "require",
        "command_timeout": 30,
    },
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency: yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables and seed default data."""
    from app.models import user, env_var, log_entry, audit_log, bot_config, bot_data  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")
    await _seed_default_data()


async def _seed_default_data():
    """Create default admin user and panel config if they don't exist."""
    from app.models.user import User
    from app.models.bot_config import BotConfig
    from app.core.security import hash_password
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Check if admin user exists
        result = await session.execute(
            select(User).where(User.username == settings.DEFAULT_ADMIN_USERNAME)
        )
        if not result.scalar_one_or_none():
            admin = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                is_admin=True,
                email=None,
            )
            session.add(admin)
            logger.info("Created default admin user: %s", settings.DEFAULT_ADMIN_USERNAME)

        # Check if bot config exists
        result2 = await session.execute(select(BotConfig).limit(1))
        if not result2.scalar_one_or_none():
            config = BotConfig(
                bot_name="My Discord Bot",
                main_file="main.py",
                auto_restart=False,
                auto_install_deps=True,
                max_log_lines=1000,
                python_version="3.13",
            )
            session.add(config)
            logger.info("Created default bot config.")

        await session.commit()
