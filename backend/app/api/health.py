"""Health check endpoint (seção 47) — unversioned, unauthenticated.

Used by load balancers/orchestrators for liveness/readiness, by the
desktop client to render the 🟢 Conectado / 🔴 Offline indicator (seção 32),
e pela tela Configurações (seção 26) pra mostrar em qual banco o backend
está falando de verdade — depois de mais de uma confusão nesta mesma sessão
sobre "qual banco tá ativo agora", ter isso visível na própria tela evita
descobrir só quando algo já deu errado.
"""
from urllib.parse import urlparse

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal

router = APIRouter(tags=["health"])


def _database_host(database_url: str) -> str:
    """Só host:porta/banco — nunca usuário/senha, mesmo neste endpoint sem
    autenticação nenhuma."""
    scheme, _, rest = database_url.partition("://")
    parsed = urlparse(f"{scheme.split('+', 1)[0]}://{rest}")
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/")
    return f"{parsed.hostname or '?'}{port}/{database}"


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
        "database_host": _database_host(settings.database_url),
    }
