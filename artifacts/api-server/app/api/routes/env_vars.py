"""Environment variable management routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.env_var import EnvVar
from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/env-vars", tags=["env-vars"])


async def _audit(db: AsyncSession, user_id: int, action: str, details: str):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    db.add(AuditLog(
        user_id=user_id,
        username=user.username if user else None,
        action=action,
        details=details,
    ))
    await db.commit()


def _serialize(var: EnvVar) -> dict:
    return {
        "id": var.id,
        "key": var.key,
        "value": var.value,
        "is_secret": var.is_secret,
        "created_at": var.created_at.isoformat(),
        "updated_at": var.updated_at.isoformat(),
    }


@router.get("")
async def list_env_vars(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """List all environment variables."""
    result = await db.execute(select(EnvVar).order_by(EnvVar.key))
    vars = result.scalars().all()
    return [_serialize(v) for v in vars]


@router.post("", status_code=201)
async def create_env_var(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new environment variable."""
    body = await request.json()
    key = body.get("key", "").strip().upper()
    value = body.get("value", "")
    is_secret = body.get("is_secret", False)

    if not key:
        raise HTTPException(status_code=400, detail="Key is required")

    # Check for duplicate
    existing = await db.execute(select(EnvVar).where(EnvVar.key == key))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Environment variable '{key}' already exists")

    var = EnvVar(key=key, value=value, is_secret=is_secret)
    db.add(var)
    await db.flush()
    await db.refresh(var)
    await _audit(db, user_id, "env_var_create", f"Created env var: {key}")

    return _serialize(var)


@router.put("/{var_id}")
async def update_env_var(
    var_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update an environment variable."""
    result = await db.execute(select(EnvVar).where(EnvVar.id == var_id))
    var = result.scalar_one_or_none()
    if not var:
        raise HTTPException(status_code=404, detail="Environment variable not found")

    body = await request.json()
    if "key" in body:
        var.key = body["key"].strip().upper()
    if "value" in body:
        var.value = body["value"]
    if "is_secret" in body:
        var.is_secret = body["is_secret"]

    from datetime import datetime, timezone
    var.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(var)
    await _audit(db, user_id, "env_var_update", f"Updated env var: {var.key}")

    return _serialize(var)


@router.delete("/{var_id}")
async def delete_env_var(
    var_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete an environment variable."""
    result = await db.execute(select(EnvVar).where(EnvVar.id == var_id))
    var = result.scalar_one_or_none()
    if not var:
        raise HTTPException(status_code=404, detail="Environment variable not found")

    key = var.key
    await db.delete(var)
    await _audit(db, user_id, "env_var_delete", f"Deleted env var: {key}")

    return {"success": True, "message": f"Deleted: {key}"}
