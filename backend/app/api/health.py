"""Health check endpoint (seção 47) — unversioned, unauthenticated.

Used by load balancers/orchestrators for liveness/readiness, and by the
desktop client to render the 🟢 Conectado / 🔴 Offline indicator (seção 32).
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """Report application liveness and database reachability."""
    settings = get_settings()
    database_status = "up"
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health check must never raise
        database_status = "down"

    return {
        "status": "ok" if database_status == "up" else "degraded",
        "version": settings.app_version,
        "environment": settings.app_env,
        "database": database_status,
    }
