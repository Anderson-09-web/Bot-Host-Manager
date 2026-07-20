"""Bot process manager: start, stop, restart, kill the Discord bot subprocess."""
import asyncio
import logging
import os
import sys
import signal
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, List
import psutil
from app.core.config import settings

logger = logging.getLogger(__name__)

# Bot state constants
STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"
STATUS_STARTING = "starting"
STATUS_RESTARTING = "restarting"
STATUS_STOPPING = "stopping"

# Supported Discord frameworks
DISCORD_FRAMEWORKS = {
    "discord.py": ["discord", "discord.py"],
    "py-cord": ["discord"],
    "nextcord": ["nextcord"],
    "disnake": ["disnake"],
    "interactions.py": ["interactions"],
    "hikari": ["hikari"],
}


class BotManager:
    """Manages the lifecycle of the Discord bot subprocess."""

    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self.status: str = STATUS_OFFLINE
        self.started_at: Optional[datetime] = None
        self.main_file: str = settings.DEFAULT_MAIN_FILE
        self.framework: Optional[str] = None
        self.work_dir: Path = Path(settings.BOT_WORK_DIR)
        self._log_callbacks: List[Callable] = []
        self._console_callbacks: List[Callable] = []
        self._stdout_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._auto_restart_task: Optional[asyncio.Task] = None

    def add_log_callback(self, callback: Callable):
        """Register a callback to receive log lines (stored to DB)."""
        self._log_callbacks.append(callback)

    def add_console_callback(self, callback: Callable):
        """Register a WebSocket callback for real-time console streaming."""
        self._console_callbacks.append(callback)

    def remove_console_callback(self, callback: Callable):
        """Unregister a WebSocket console callback."""
        self._console_callbacks = [c for c in self._console_callbacks if c != callback]

    async def _broadcast_log(self, message: str, level: str = "INFO"):
        """Send a log line to all registered callbacks."""
        for cb in self._log_callbacks:
            try:
                await cb(message, level)
            except Exception:
                pass
        for cb in self._console_callbacks:
            try:
                await cb({"type": "log", "level": level, "message": message,
                          "timestamp": datetime.now(timezone.utc).isoformat()})
            except Exception:
                pass

    async def _broadcast_status(self):
        """Broadcast current status to WebSocket clients."""
        status_data = self.get_status_dict()
        for cb in self._console_callbacks:
            try:
                await cb({"type": "status", "data": status_data})
            except Exception:
                pass

    def get_status_dict(self) -> dict:
        """Return current bot status as a dict."""
        uptime = None
        if self.started_at and self.status == STATUS_ONLINE:
            uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()

        pid = self.process.pid if self.process and self.process.returncode is None else None
        memory_mb = None
        cpu_percent = None

        if pid:
            try:
                proc = psutil.Process(pid)
                mem = proc.memory_info()
                memory_mb = mem.rss / (1024 * 1024)
                cpu_percent = proc.cpu_percent(interval=0.1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "status": self.status,
            "pid": pid,
            "uptime_seconds": uptime,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "framework": self.framework,
            "main_file": self.main_file,
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
        }

    async def sync_files_from_r2(self):
        """Download all bot files from R2 to the work directory."""
        from app.services.r2_service import r2_service

        self.work_dir.mkdir(parents=True, exist_ok=True)
        await self._broadcast_log("Syncing files from Cloudflare R2...", "INFO")

        try:
            objects = await r2_service.list_objects(prefix="")
            for obj in objects:
                key = obj["Key"]
                local_path = self.work_dir / key
                local_path.parent.mkdir(parents=True, exist_ok=True)
                data = await r2_service.get_object(key)
                if data is not None:
                    local_path.write_bytes(data)

            await self._broadcast_log(f"Synced {len(objects)} files from R2.", "INFO")
        except Exception as e:
            logger.error("Failed to sync files from R2: %s", e)
            await self._broadcast_log(f"R2 sync failed: {e}", "ERROR")

    async def install_dependencies(self) -> bool:
        """Install requirements.txt if present."""
        req_file = self.work_dir / "requirements.txt"
        if not req_file.exists():
            await self._broadcast_log("No requirements.txt found, skipping install.", "INFO")
            return True

        await self._broadcast_log("Installing dependencies from requirements.txt...", "INFO")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", "-r", str(req_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(self.work_dir),
            )
            async for line in proc.stdout:
                msg = line.decode("utf-8", errors="replace").rstrip()
                if msg:
                    await self._broadcast_log(msg, "INFO")
            await proc.wait()
            if proc.returncode == 0:
                await self._broadcast_log("Dependencies installed successfully.", "INFO")
                return True
            else:
                await self._broadcast_log("pip install failed.", "ERROR")
                return False
        except Exception as e:
            logger.error("install_dependencies error: %s", e)
            await self._broadcast_log(f"Install error: {e}", "ERROR")
            return False

    def detect_framework(self) -> Optional[str]:
        """Detect the Discord framework from requirements.txt."""
        req_file = self.work_dir / "requirements.txt"
        if not req_file.exists():
            return None
        content = req_file.read_text().lower()
        for framework, keywords in DISCORD_FRAMEWORKS.items():
            if any(kw in content for kw in keywords):
                return framework
        return None

    def detect_main_file(self, configured: str) -> Optional[str]:
        """Find the main Python file to run."""
        candidates = [configured, "main.py", "bot.py", "index.py", "run.py", "app.py"]
        for candidate in candidates:
            path = self.work_dir / candidate
            if path.exists() and path.suffix == ".py":
                return candidate
        # Look for any .py file
        py_files = list(self.work_dir.glob("*.py"))
        if py_files:
            return py_files[0].name
        return None

    async def start(self, main_file: str = None, auto_install: bool = True) -> bool:
        """Start the bot subprocess."""
        if self.status in (STATUS_ONLINE, STATUS_STARTING, STATUS_RESTARTING):
            await self._broadcast_log("Bot is already running.", "WARNING")
            return False

        self.status = STATUS_STARTING
        await self._broadcast_status()

        try:
            # Sync files from R2
            await self.sync_files_from_r2()

            # Install dependencies
            if auto_install:
                await self.install_dependencies()

            # Determine main file
            target_file = main_file or self.main_file
            actual_file = self.detect_main_file(target_file)
            if not actual_file:
                await self._broadcast_log(f"Main file '{target_file}' not found.", "ERROR")
                self.status = STATUS_OFFLINE
                await self._broadcast_status()
                return False

            self.main_file = actual_file
            self.framework = self.detect_framework()

            # Build environment for bot subprocess
            env = os.environ.copy()
            # Inject stored env vars
            from app.services.env_service import env_service
            stored_vars = await env_service.get_all()
            for var in stored_vars:
                env[var["key"]] = var["value"]

            await self._broadcast_log(
                f"Starting bot: {actual_file} (framework: {self.framework or 'unknown'})", "INFO"
            )

            self.process = await asyncio.create_subprocess_exec(
                sys.executable, actual_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.work_dir),
                env=env,
            )

            self.started_at = datetime.now(timezone.utc)
            self.status = STATUS_ONLINE
            await self._broadcast_status()

            # Stream stdout and stderr
            self._stdout_task = asyncio.create_task(self._stream_stdout())
            self._stderr_task = asyncio.create_task(self._stream_stderr())
            self._auto_restart_task = asyncio.create_task(self._monitor_process())

            await self._broadcast_log(f"Bot started with PID {self.process.pid}", "INFO")
            return True

        except Exception as e:
            logger.error("Failed to start bot: %s", e)
            await self._broadcast_log(f"Failed to start bot: {e}", "ERROR")
            self.status = STATUS_OFFLINE
            self.process = None
            await self._broadcast_status()
            return False

    async def _stream_stdout(self):
        """Stream bot stdout to console callbacks."""
        if not self.process or not self.process.stdout:
            return
        try:
            async for line in self.process.stdout:
                msg = line.decode("utf-8", errors="replace").rstrip()
                if msg:
                    await self._broadcast_log(msg, "INFO")
        except Exception as e:
            logger.debug("stdout stream ended: %s", e)

    async def _stream_stderr(self):
        """Stream bot stderr to console callbacks."""
        if not self.process or not self.process.stderr:
            return
        try:
            async for line in self.process.stderr:
                msg = line.decode("utf-8", errors="replace").rstrip()
                if msg:
                    level = "ERROR" if "error" in msg.lower() or "exception" in msg.lower() else "WARNING"
                    await self._broadcast_log(msg, level)
        except Exception as e:
            logger.debug("stderr stream ended: %s", e)

    async def _monitor_process(self):
        """Monitor bot process; auto-restart if configured."""
        from app.core.database import AsyncSessionLocal
        from app.models.bot_config import BotConfig
        from sqlalchemy import select

        if not self.process:
            return
        returncode = await self.process.wait()

        if self.status in (STATUS_STOPPING,):
            return  # Intentional stop

        await self._broadcast_log(f"Bot process exited with code {returncode}.", "WARNING")
        self.status = STATUS_OFFLINE
        self.started_at = None
        await self._broadcast_status()

        # Check auto-restart config
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(BotConfig).limit(1))
                config = result.scalar_one_or_none()
                if config and config.auto_restart and returncode != 0:
                    await self._broadcast_log("Auto-restarting bot in 5 seconds...", "INFO")
                    await asyncio.sleep(5)
                    await self.start(auto_install=False)
        except Exception as e:
            logger.error("Auto-restart error: %s", e)

    async def stop(self) -> bool:
        """Gracefully stop the bot."""
        if not self.process or self.status == STATUS_OFFLINE:
            await self._broadcast_log("Bot is not running.", "WARNING")
            return False

        self.status = STATUS_STOPPING
        await self._broadcast_status()
        await self._broadcast_log("Stopping bot...", "INFO")

        try:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                self.process.kill()

            self.status = STATUS_OFFLINE
            self.started_at = None
            self.process = None
            await self._broadcast_log("Bot stopped.", "INFO")
            await self._broadcast_status()
            return True
        except Exception as e:
            logger.error("Stop error: %s", e)
            await self._broadcast_log(f"Stop error: {e}", "ERROR")
            return False

    async def restart(self, main_file: str = None) -> bool:
        """Restart the bot."""
        self.status = STATUS_RESTARTING
        await self._broadcast_status()
        await self._broadcast_log("Restarting bot...", "INFO")

        if self.process:
            await self.stop()
        await asyncio.sleep(1)
        return await self.start(main_file=main_file, auto_install=True)

    async def kill(self) -> bool:
        """Force kill the bot process."""
        if not self.process:
            await self._broadcast_log("Bot is not running.", "WARNING")
            return False

        try:
            self.process.kill()
            self.status = STATUS_OFFLINE
            self.started_at = None
            self.process = None
            await self._broadcast_log("Bot force-killed.", "WARNING")
            await self._broadcast_status()
            return True
        except Exception as e:
            logger.error("Kill error: %s", e)
            await self._broadcast_log(f"Kill error: {e}", "ERROR")
            return False


# Singleton
bot_manager = BotManager()
