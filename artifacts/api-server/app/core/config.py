"""Application configuration using Pydantic Settings."""
import os
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Discord Bot Hosting Panel"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database (Neon PostgreSQL)
    NEON_DATABASE_URL: str = ""

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_ENDPOINT_URL: str = ""

    # Security
    ALLOWED_HOSTS: str = "*"
    CORS_ORIGINS: str = "*"

    # Bot
    BOT_WORK_DIR: str = "/tmp/bot_workspace"
    DEFAULT_MAIN_FILE: str = "main.py"

    # Panel
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"

    @property
    def async_database_url(self) -> str:
        """Convert postgres:// to postgresql+asyncpg:// for async SQLAlchemy."""
        url = self.NEON_DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        # Remove sslmode from URL (asyncpg handles it differently)
        if "?sslmode=" in url:
            url = url.split("?sslmode=")[0]
        return url

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
