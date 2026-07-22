"""File system routes backed by Cloudflare R2."""
import logging
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import PurePosixPath
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.r2_storage import r2_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


def _normalize(path: str) -> str:
    """Normalize a path: strip leading slash for R2 key usage."""
    return path.lstrip("/")


def _ext(name: str) -> str | None:
    parts = name.rsplit(".", 1)
    return parts[1] if len(parts) == 2 else None


def _is_folder_key(key: str) -> bool:
    return key.endswith("/") or not os.path.splitext(key)[1]


async def _audit(db: AsyncSession, user_id: int, action: str, details: str):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    db.add(AuditLog(
        user_id=user_id,
        username=user.username if user else None,
        action=action,
        details=details,
        ip_address=None,
    ))
    await db.commit()


@router.get("")
async def list_files(
    path: str = "/",
    user_id: int = Depends(get_current_user_id),
):
    """List files and folders at the given path from R2."""
    prefix = _normalize(path)
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    try:
        response = await r2_service.list_prefix(prefix=prefix, delimiter="/")
    except Exception as e:
        logger.error("list_files error: %s", e)
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")

    items = []

    # Common prefixes = sub-folders
    for cp in response.get("CommonPrefixes", []):
        folder_key = cp.get("Prefix", "")
        name = folder_key.rstrip("/").split("/")[-1]
        if name:
            items.append({
                "name": name,
                "path": "/" + folder_key.rstrip("/"),
                "type": "folder",
                "size": None,
                "modified_at": None,
                "extension": None,
            })

    # Contents = files
    for obj in response.get("Contents", []):
        key = obj.get("Key", "")
        # Skip the prefix itself
        if key == prefix:
            continue
        name = key.split("/")[-1]
        if not name:
            continue
        last_mod = obj.get("LastModified")
        items.append({
            "name": name,
            "path": "/" + key,
            "type": "file",
            "size": obj.get("Size", 0),
            "modified_at": last_mod.isoformat() if last_mod else None,
            "extension": _ext(name),
        })

    files = [i for i in items if i["type"] == "file"]
    folders = [i for i in items if i["type"] == "folder"]

    return {
        "path": "/" + prefix.rstrip("/") if prefix else "/",
        "items": sorted(folders, key=lambda x: x["name"]) + sorted(files, key=lambda x: x["name"]),
        "total_files": len(files),
        "total_folders": len(folders),
    }


@router.get("/content")
async def get_file_content(
    path: str,
    user_id: int = Depends(get_current_user_id),
):
    """Get the text content of a file from R2."""
    key = _normalize(path)
    data = await r2_service.get_object(key)
    if data is None:
        raise HTTPException(status_code=404, detail="File not found")

    metadata = await r2_service.get_object_metadata(key)

    try:
        content = data.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        content = data.decode("latin-1", errors="replace")
        encoding = "latin-1"

    return {
        "path": path,
        "content": content,
        "encoding": encoding,
        "size": len(data),
        "modified_at": metadata["last_modified"].isoformat() if metadata and metadata.get("last_modified") else None,
    }


@router.put("/content")
async def update_file_content(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Save file content to R2."""
    body = await request.json()
    path = body.get("path", "")
    content = body.get("content", "")

    if not path:
        raise HTTPException(status_code=400, detail="Path is required")

    key = _normalize(path)
    mime, _ = mimetypes.guess_type(path)
    data = content.encode("utf-8")
    success = await r2_service.put_object(key, data, content_type=mime or "text/plain")
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save file")

    await _audit(db, user_id, "file_save", f"Saved {path} ({len(data)} bytes)")
    return {"success": True, "message": f"File saved: {path}"}


@router.post("/create", status_code=201)
async def create_file(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new file or folder in R2."""
    body = await request.json()
    path = body.get("path", "")
    file_type = body.get("type", "file")
    content = body.get("content", "")

    if not path:
        raise HTTPException(status_code=400, detail="Path is required")

    key = _normalize(path)

    if file_type == "folder":
        # Folders are represented by a zero-byte object with trailing slash
        folder_key = key.rstrip("/") + "/"
        await r2_service.put_object(folder_key, b"", content_type="application/x-directory")
        name = folder_key.rstrip("/").split("/")[-1]
        await _audit(db, user_id, "folder_create", f"Created folder: {path}")
        return {
            "name": name,
            "path": "/" + folder_key.rstrip("/"),
            "type": "folder",
            "size": None,
            "modified_at": None,
            "extension": None,
        }
    else:
        data = content.encode("utf-8") if content else b""
        mime, _ = mimetypes.guess_type(path)
        await r2_service.put_object(key, data, content_type=mime or "text/plain")
        name = key.split("/")[-1]
        await _audit(db, user_id, "file_create", f"Created file: {path}")
        return {
            "name": name,
            "path": "/" + key,
            "type": "file",
            "size": len(data),
            "modified_at": datetime.now(timezone.utc).isoformat(),
            "extension": _ext(name),
        }


@router.delete("")
async def delete_file(
    path: str,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a file or folder (and all its contents) from R2.

    When a Python cog file (``cogs/*.py``) is deleted, all bot_data
    entries stored under that cog's namespace are also purged so that
    a new cog with the same name starts with a clean slate.
    """
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")

    key = _normalize(path)
    # Try as exact file first
    if await r2_service.object_exists(key):
        await r2_service.delete_object(key)
        # Also delete the compiled .pyc from __pycache__ so Python doesn't
        # load a stale bytecode version after the source file is removed.
        await _delete_pycache_for(key)
        await _audit(db, user_id, "file_delete", f"Deleted file: {path}")
        # Purge bot_data for this cog module (only for cogs/*.py)
        await _purge_cog_bot_data(db, key)
    else:
        # Try as folder prefix
        prefix = key.rstrip("/") + "/"
        deleted = await r2_service.delete_prefix(prefix)
        if deleted == 0:
            raise HTTPException(status_code=404, detail="File or folder not found")
        await _audit(db, user_id, "folder_delete", f"Deleted folder: {path} ({deleted} objects)")

    return {"success": True, "message": f"Deleted: {path}"}


async def _delete_pycache_for(r2_key: str):
    """Delete the compiled .pyc in __pycache__ that matches a .py source key.

    When a .py file lives at ``parent/__pycache__/<stem>.cpython-*.pyc``,
    Python can still import the cached bytecode even after the source is gone.
    We proactively delete all matching .pyc files from R2 on every .py delete
    so the bot never loads a stale cog.

    Example: ``cogs/logs.py`` → deletes ``cogs/__pycache__/logs.cpython-*.pyc``
    """
    from pathlib import PurePosixPath
    p = PurePosixPath(r2_key)
    if p.suffix != ".py":
        return
    pycache_prefix = str(p.parent / "__pycache__" / p.stem)
    try:
        objects = await r2_service.list_objects(prefix=pycache_prefix)
        pyc_keys = [{"Key": o["Key"]} for o in objects if o["Key"].endswith(".pyc")]
        if pyc_keys:
            # delete_prefix handles batching; we reuse delete_object for each
            for item in pyc_keys:
                await r2_service.delete_object(item["Key"])
            logger.info("Deleted %d .pyc file(s) for %s", len(pyc_keys), r2_key)
    except Exception as e:
        logger.warning("Could not delete __pycache__ for %s: %s", r2_key, e)


async def _purge_cog_bot_data(db: AsyncSession, r2_key: str):
    """If *r2_key* looks like ``cogs/<name>.py``:
    1. Delete all bot_data rows whose key starts with ``<name>/``
       so stale config is gone immediately.
    2. Delete all log_entry rows that mention the cog module name
       so stale/error logs from the deleted cog stop appearing.
    3. If the bot is currently running, restart it so the cog is
       unloaded from memory and can no longer produce new errors.
    """
    from pathlib import PurePosixPath
    from sqlalchemy import delete as sql_delete
    from app.models.bot_data import BotData
    from app.models.log_entry import LogEntry

    p = PurePosixPath(r2_key)
    # Only act on cog Python files (cogs/<something>.py)
    if p.parent.name != "cogs" or p.suffix != ".py":
        return

    module_name = p.stem

    # 1. Purge bot_data config for this cog
    prefix = f"{module_name}/"
    result = await db.execute(
        sql_delete(BotData).where(BotData.key.like(f"{prefix}%"))
    )
    await db.commit()
    if result.rowcount:
        logger.info("Purged %d bot_data row(s) for deleted cog '%s'", result.rowcount, module_name)

    # 2. Purge log entries mentioning this cog so stale errors don't linger
    log_patterns = [
        f"%cogs.{module_name}%",
        f"%cog: cogs.{module_name}%",
        f"[{module_name}]%",
    ]
    from sqlalchemy import or_
    log_result = await db.execute(
        sql_delete(LogEntry).where(
            or_(*(LogEntry.message.ilike(pat) for pat in log_patterns))
        )
    )
    await db.commit()
    if log_result.rowcount:
        logger.info("Purged %d log row(s) mentioning deleted cog '%s'", log_result.rowcount, module_name)

    # 3. Restart the bot if it's running so the cog is unloaded from memory
    try:
        from app.services.bot_manager import bot_manager, STATUS_ONLINE, STATUS_STARTING, STATUS_RESTARTING
        if bot_manager.status in (STATUS_ONLINE, STATUS_STARTING, STATUS_RESTARTING):
            logger.info("Restarting bot to unload deleted cog '%s'", module_name)
            import asyncio
            asyncio.create_task(bot_manager.restart())
    except Exception as e:
        logger.warning("Could not schedule bot restart after cog deletion: %s", e)


@router.post("/rename")
async def rename_file(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Rename a file or folder in R2 (copy + delete)."""
    body = await request.json()
    path = body.get("path", "")
    new_name = body.get("new_name", "")

    if not path or not new_name:
        raise HTTPException(status_code=400, detail="path and new_name are required")

    source_key = _normalize(path)
    parent = "/".join(source_key.split("/")[:-1])
    dest_key = (parent + "/" + new_name).lstrip("/")

    is_file = await r2_service.object_exists(source_key)
    if is_file:
        await r2_service.copy_object(source_key, dest_key)
        await r2_service.delete_object(source_key)
    else:
        # Rename folder: copy all objects, delete old prefix
        old_prefix = source_key.rstrip("/") + "/"
        new_prefix = dest_key.rstrip("/") + "/"
        objects = await r2_service.list_objects(prefix=old_prefix)
        for obj in objects:
            old_key = obj["Key"]
            new_key = new_prefix + old_key[len(old_prefix):]
            await r2_service.copy_object(old_key, new_key)
        await r2_service.delete_prefix(old_prefix)

    await _audit(db, user_id, "file_rename", f"Renamed {path} → {new_name}")
    return {"success": True, "message": f"Renamed to {new_name}"}


@router.post("/move")
async def move_file(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Move a file or folder to a new location in R2."""
    body = await request.json()
    source = body.get("source", "")
    destination = body.get("destination", "")

    if not source or not destination:
        raise HTTPException(status_code=400, detail="source and destination are required")

    source_key = _normalize(source)
    dest_key = _normalize(destination)

    is_file = await r2_service.object_exists(source_key)
    if is_file:
        await r2_service.copy_object(source_key, dest_key)
        await r2_service.delete_object(source_key)
    else:
        old_prefix = source_key.rstrip("/") + "/"
        new_prefix = dest_key.rstrip("/") + "/"
        objects = await r2_service.list_objects(prefix=old_prefix)
        for obj in objects:
            old_k = obj["Key"]
            new_k = new_prefix + old_k[len(old_prefix):]
            await r2_service.copy_object(old_k, new_k)
        await r2_service.delete_prefix(old_prefix)

    await _audit(db, user_id, "file_move", f"Moved {source} → {destination}")
    return {"success": True, "message": f"Moved to {destination}"}


@router.post("/copy", status_code=201)
async def copy_file(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Copy a file or folder within R2."""
    body = await request.json()
    source = body.get("source", "")
    destination = body.get("destination", "")

    if not source or not destination:
        raise HTTPException(status_code=400, detail="source and destination are required")

    source_key = _normalize(source)
    dest_key = _normalize(destination)

    is_file = await r2_service.object_exists(source_key)
    if is_file:
        ok = await r2_service.copy_object(source_key, dest_key)
        if not ok:
            raise HTTPException(status_code=500, detail="Copy failed")
    else:
        old_prefix = source_key.rstrip("/") + "/"
        new_prefix = dest_key.rstrip("/") + "/"
        objects = await r2_service.list_objects(prefix=old_prefix)
        for obj in objects:
            old_k = obj["Key"]
            new_k = new_prefix + old_k[len(old_prefix):]
            await r2_service.copy_object(old_k, new_k)

    await _audit(db, user_id, "file_copy", f"Copied {source} → {destination}")
    return {"success": True, "message": f"Copied to {destination}"}


@router.post("/upload", status_code=201)
async def upload_file(
    path: str = Form(...),
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file to R2."""
    data = await file.read()
    filename = file.filename or "upload"

    # Build destination key
    dest_path = path.rstrip("/") + "/" + filename if path.rstrip("/") else filename
    key = _normalize(dest_path)

    mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    ok = await r2_service.put_object(key, data, content_type=mime)
    if not ok:
        raise HTTPException(status_code=500, detail="Upload to R2 failed")

    await _audit(db, user_id, "file_upload", f"Uploaded {filename} to /{key} ({len(data)} bytes)")

    return {
        "name": filename,
        "path": "/" + key,
        "type": "file",
        "size": len(data),
        "modified_at": datetime.now(timezone.utc).isoformat(),
        "extension": _ext(filename),
    }


@router.get("/download")
async def download_file(
    path: str,
    user_id: int = Depends(get_current_user_id),
):
    """Stream a file from R2 as a download."""
    key = _normalize(path)
    data = await r2_service.get_object(key)
    if data is None:
        raise HTTPException(status_code=404, detail="File not found")

    filename = key.split("/")[-1]
    mime, _ = mimetypes.guess_type(filename)

    return Response(
        content=data,
        media_type=mime or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
