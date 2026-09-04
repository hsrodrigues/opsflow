"""Application configuration.

All configuration is loaded from environment variables (via a `.env` file in
development). Nothing sensitive is ever hardcoded here — see `.env.example`
for the full list of variables a deployment must provide.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed application settings, populated from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    app_name: str = "OpsFlow API"
    app_env: Literal["development", "staging", "production"] = "development"
    app_version: str = "1.0.0"
    debug: bool = False

    # --- Database ---
    database_url: str = Field(
        default="mysql+pymysql://root:@127.0.0.1:3306/opsflow_db",
        description="SQLAlchemy connection string.",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 1800

    # --- Security / JWT ---
    jwt_secret: str = Field(
        default=...,
        description="Secret used to sign JWTs. MUST be overridden in every environment.",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    password_reset_token_expire_minutes: int = 30
    max_login_attempts: int = 5
    login_lockout_minutes: int = 15

    # --- Redis (reserved for future Celery migration; unused by the MVP) ---
    redis_url: str | None = None

    # --- API ---
    api_v1_prefix: str = "/api/v1"
    cors_allow_origins: list[str] = ["*"]
    rate_limit_per_minute: int = 120

    # --- License server ---
    license_server_url: str | None = None

    # --- SMTP (email) ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str = "no-reply@opsflow.local"
    smtp_use_tls: bool = True

    # --- Logging ---
    log_dir: str = "logs"
    log_level: str = "INFO"

    # --- Seed de demonstração (database/seeds/seed_demo.py) ---
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance (loaded once per process)."""
    return Settings()
