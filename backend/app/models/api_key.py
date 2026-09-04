"""API key model (seção 23/41) — machine credentials for integrations.

Only a hash of the key is stored, the same way passwords and refresh tokens
are handled: a database leak alone must never be enough to authenticate.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin
from app.models.types import bigint_pk


class ApiKey(Base, TimestampMixin, TenantMixin):
    """A named API credential a tenant can issue for external integrations."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ApiKey id={self.id} name={self.name!r}>"
