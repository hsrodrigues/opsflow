"""Audit log model (seção 19).

`tenant_id` is nullable because a `SUPER_ADMIN` action (e.g. creating a
tenant) has no tenant of its own. Written exclusively through the audit
service (Fase 2), which is also the only writer of `logs/audit.log` (see
`app/core/logging_config.py`) — this table is the queryable counterpart of
that same trail.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AuditAction
from app.models.types import bigint_pk, enum_column


class AuditLog(Base):
    """One recorded audit event."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    action: Mapped[AuditAction] = mapped_column(enum_column(AuditAction, length=20), nullable=False)
    table_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    record_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AuditLog id={self.id} action={self.action} table={self.table_name!r}>"
