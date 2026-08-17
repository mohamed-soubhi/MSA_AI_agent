"""Health check endpoints -- what Nginx/uptime monitors/load balancers
poll to decide if this instance is alive and should keep receiving
traffic.
"""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe: process is up and can serve requests."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }
