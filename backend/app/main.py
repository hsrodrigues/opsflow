"""FastAPI application entry point.

Run with: `uvicorn app.main:app --reload` (from `backend/`), or via
`python -m app.main` for a plain run without the reloader.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.jobs.scheduler import start_scheduler, stop_scheduler

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Plataforma de gestão operacional e logística multi-tenant.",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.allowed_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(SecurityHeadersMiddleware)
if settings.rate_limiting_enabled:
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute)

register_exception_handlers(app)

app.include_router(health_router, prefix="/api")
app.include_router(api_router, prefix=settings.api_v1_prefix)

_PANEL_HTML_PATH = Path(__file__).resolve().parent / "static" / "panel.html"


@app.get("/painel/{token}", response_class=HTMLResponse, include_in_schema=False)
def serve_panel(token: str) -> HTMLResponse:
    """Serves the TV painel page — a single static HTML for any token; the
    page's own JS reads the token back out of the URL and calls
    `/api/v1/panel/{token}/board` (the actual authenticated-by-token data
    endpoint) to render it. Not templated server-side on purpose: keeps this
    route trivial and cacheable, with zero server-side state per request."""
    return HTMLResponse(_PANEL_HTML_PATH.read_text(encoding="utf-8"))


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "OpsFlow API iniciada | versão=%s ambiente=%s",
        settings.app_version,
        settings.app_env,
    )
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_scheduler()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.app_env == "development")
