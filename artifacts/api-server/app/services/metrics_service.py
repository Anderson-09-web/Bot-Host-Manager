"""System metrics collection using psutil."""
import asyncio
import platform
import sys
import time
from datetime import datetime, timezone
from typing import Optional
import psutil
from app.services.bot_manager import bot_manager


_start_time = time.time()


async def collect_metrics(file_count: int = 0, folder_count: int = 0) -> dict:
    """Collect current system metrics snapshot."""
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime = time.time() - _start_time

    bot_status = bot_manager.get_status_dict()

    return {
        "cpu_percent": round(cpu, 2),
        "ram_used_mb": round(mem.used / (1024 * 1024), 2),
        "ram_total_mb": round(mem.total / (1024 * 1024), 2),
        "ram_percent": round(mem.percent, 2),
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_percent": round(disk.percent, 2),
        "uptime_seconds": round(uptime, 2),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "bot_status": bot_status["status"],
        "bot_pid": bot_status.get("pid"),
        "bot_uptime_seconds": bot_status.get("uptime_seconds"),
        "bot_memory_mb": bot_status.get("memory_mb"),
        "bot_cpu_percent": bot_status.get("cpu_percent"),
        "file_count": file_count,
        "folder_count": folder_count,
        "latency_ms": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
