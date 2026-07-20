"""Re-export r2_service singleton for consistent import paths."""
from app.services.r2_storage import r2_service

__all__ = ["r2_service"]
