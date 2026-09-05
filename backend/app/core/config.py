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
    # Desligado só pelos testes automatizados (`conftest.py`) — 100+
    # requests numa suíte de verdade bateria no limite e derrubaria testes
    # que não têm nada a ver com rate limiting.
    rate_limiting_enabled: bool = True
    # Host(s) que a API aceita servir — `["*"]` (default) não restringe
    # nada; numa API atrás de um domínio público fixo, liste-o aqui pra
    # mitigar ataques de Host header (cache poisoning, links de reset de
    # senha forjados com outro host, etc. — nenhum destes é explorável hoje
    # nesta aplicação especificamente, mas é a mitigação padrão).
    allowed_hosts: list[str] = ["*"]

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

    # --- Jobs em background (seção 41 "Automações" — app/jobs/) ---
    jobs_enabled: bool = True
    delay_detection_interval_minutes: int = 5
    cnh_alert_interval_hours: int = 24
    license_expiration_interval_minutes: int = 60
    stale_operations_interval_minutes: int = 60
    stale_operation_hours: int = 24

    # --- Backup do banco (app/jobs/backup_job.py) ---
    backup_dir: str = "backups"
    backup_interval_hours: int = 24
    backup_retention_count: int = 14
    # Só necessário no Windows quando `mysqldump`/`mysql` não estão no PATH
    # (instalação padrão do MySQL Installer não adiciona ao PATH do sistema).
    # Em Docker/Linux, deixe em branco — os binários já estão no PATH do
    # container.
    mysql_bin_dir: str | None = None

    @property
    def cors_allow_credentials(self) -> bool:
        """`allow_credentials=True` combinado com `allow_origins=["*"]` é
        uma combinação que o próprio spec de CORS considera inválida (a
        maioria dos navegadores recusa/ignora credenciais nesse caso de
        qualquer forma) — só liga quando a lista de origens já foi
        restringida a domínios específicos."""
        return self.cors_allow_origins != ["*"]

    @property
    def docs_enabled(self) -> bool:
        """`/docs`/`/redoc`/`/openapi.json` publicam o contrato inteiro da
        API (todo endpoint, todo schema) sem exigir autenticação — sem
        problema em desenvolvimento, um vazamento de informação
        desnecessário numa API real na internet. `@property` (não um campo
        de env var) de propósito: nunca configurável por engano, sempre
        derivado de `app_env`.
        """
        return self.app_env != "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance (loaded once per process)."""
    return Settings()
