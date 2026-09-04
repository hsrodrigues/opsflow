"""System settings model (seção 40).

`tenant_id=None` stores a platform-wide default; a tenant-specific row (same
`key`, non-null `tenant_id`) overrides it. Values are stored as JSON so a
single table can hold booleans, numbers, strings or small objects without a
schema change per setting.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import bigint_pk


class SystemSetting(Base):
    """A single key/value configuration entry, global or tenant-scoped."""

    __tablename__ = "system_settings"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_system_settings_tenant_key"),)

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict | list | str | float | bool | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<SystemSetting id={self.id} key={self.key!r}>"
