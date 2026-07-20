"""Health check route."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def health_check():
    """Returns server health status."""
    return {"status": "ok"}
