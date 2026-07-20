"""System metrics route."""
import logging
from fastapi import APIRouter, Depends
from app.core.security import get_current_user_id
from app.services.metrics_service import collect_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def get_metrics(user_id: int = Depends(get_current_user_id)):
    """Return a real-time snapshot of system metrics."""
    return await collect_metrics()
