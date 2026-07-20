"""Authentication routes: login, logout, profile."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import (
    verify_password, create_access_token, get_current_user_id
)
from app.models.user import User
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED_ATTEMPTS = 10


@router.post("/login")
async def login(request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token."""
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    # Fetch user
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check lockout
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=429, detail="Account temporarily locked. Try again later.")

    # Verify password
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            from datetime import timedelta
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            await db.commit()
            raise HTTPException(status_code=429, detail="Too many failed attempts. Account locked for 15 minutes.")
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Reset failed attempts on success
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    # Create token
    token = create_access_token({"sub": str(user.id), "username": user.username})

    # Audit log
    ip = request.client.host if request.client else "unknown"
    db.add(AuditLog(
        user_id=user.id,
        username=user.username,
        action="login",
        details=f"Successful login from {ip}",
        ip_address=ip,
    ))
    await db.commit()

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat(),
        },
    }


@router.post("/logout")
async def logout(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Logout the current user (client discards token)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    ip = request.client.host if request.client else "unknown"
    db.add(AuditLog(
        user_id=user_id,
        username=user.username if user else None,
        action="logout",
        details=f"Logout from {ip}",
        ip_address=ip,
    ))
    await db.commit()

    return {"success": True, "message": "Logged out successfully"}


@router.get("/me")
async def get_me(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return the current authenticated user's profile."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    }
