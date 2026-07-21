"""
Discord Bot Hosting Panel — FastAPI Backend
Main application entrypoint: middleware, routers, WebSockets, startup/shutdown.
"""
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


async def _seed_default_bot_files():
    """Upload default bot files to R2 on startup.

    config_manager.py  → always overwritten (utility module, keep latest).
    All other files    → only uploaded when absent (respect user edits).
    """
    from app.services.r2_storage import r2_service
    from app.services.default_bot_files import DEFAULT_FILES

    for r2_key, (content, always_update) in DEFAULT_FILES.items():
        try:
            exists = await r2_service.object_exists(r2_key)
            if exists and not always_update:
                continue
            data = content.encode("utf-8")
            await r2_service.put_object(r2_key, data, content_type="text/plain; charset=utf-8")
            action = "Updated" if exists else "Seeded"
            logger.info("%s default bot file: %s", action, r2_key)
        except Exception as e:
            logger.warning("Could not seed %s: %s", r2_key, e)

# Configure structured logging before anything else
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── Route imports ────────────────────────────────────────────────────────────
from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.bot import router as bot_router
from app.api.routes.files import router as files_router
from app.api.routes.env_vars import router as env_vars_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.logs import router as logs_router
from app.api.routes.config import router as config_router
from app.api.routes.audit import router as audit_router
from app.api.routes.bot_data import router as bot_data_router
from app.api.websockets.console import console_websocket_handler
from app.api.websockets.metrics import metrics_websocket_handler


# ── DB log storage callback ──────────────────────────────────────────────────
async def _store_log_to_db(message: str, level: str):
    """Persist bot log lines to the database (called from bot_manager)."""
    from app.core.database import AsyncSessionLocal
    from app.models.log_entry import LogEntry
    async with AsyncSessionLocal() as session:
        session.add(LogEntry(
            level=level.upper(),
            message=message[:4000],  # Truncate very long lines
            source="bot",
        ))
        await session.commit()


# ── Startup / Shutdown ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB, register callbacks."""
    logger.info("Starting Discord Bot Hosting Panel API...")

    # Initialize database (create tables, seed defaults)
    try:
        from app.core.database import init_db
        await init_db()
        logger.info("Database ready.")
    except Exception as e:
        logger.error("Database init failed: %s — continuing anyway.", e)

    # Register DB log callback with bot manager
    from app.services.bot_manager import bot_manager
    bot_manager.add_log_callback(_store_log_to_db)

    # Seed default bot files to R2 (config_manager.py always, others only if absent)
    try:
        await _seed_default_bot_files()
    except Exception as e:
        logger.warning("Default bot file seeding failed (non-fatal): %s", e)

    logger.info("Panel API ready on port %s.", settings.__dict__.get("PORT", "?"))
    yield

    # Shutdown: stop bot if running
    from app.services.bot_manager import bot_manager, STATUS_OFFLINE
    if bot_manager.status != STATUS_OFFLINE:
        logger.info("Stopping bot on shutdown...")
        await bot_manager.stop()

    logger.info("Shutdown complete.")


# ── Security headers middleware ───────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response


# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Discord Bot Hosting Panel API",
    description="Professional hosting panel for Python Discord bots",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS — allow the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)


# ── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── REST Routers (all prefixed with /api) ────────────────────────────────────
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(bot_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(env_vars_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(logs_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(bot_data_router, prefix="/api")


# ── WebSocket endpoints ──────────────────────────────────────────────────────
@app.websocket("/api/ws/console")
async def ws_console(websocket: WebSocket):
    """Real-time bot console output over WebSocket."""
    await console_websocket_handler(websocket)


@app.websocket("/api/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    """Real-time system metrics stream over WebSocket."""
    await metrics_websocket_handler(websocket)


# ── Root redirect ────────────────────────────────────────────────────────────
@app.get("/api")
async def api_root():
    return {
        "name": "Discord Bot Hosting Panel API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/api/docs",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Static frontend (production / Render) ────────────────────────────────────
# Mounted LAST so /api/* routes take priority.
# Set STATIC_FILES_DIR env var to the built React dist directory.
import os
from pathlib import Path

_static_dir = os.environ.get("STATIC_FILES_DIR", "")
if _static_dir:
    _static_path = Path(_static_dir)
    if _static_path.exists() and _static_path.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(_static_path), html=True),
            name="static",
        )
        logger.info("Serving frontend static files from: %s", _static_path.resolve())
    else:
        logger.warning("STATIC_FILES_DIR set but path not found: %s", _static_dir)
