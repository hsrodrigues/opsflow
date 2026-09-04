"""Integration config model (seção 41).

Stores configuration for a named integration adapter (SAP, Power BI,
WhatsApp, e-mail, GPS, TMS, WMS, ERP, ...). No fictitious integration is
implemented in the MVP (per the spec's explicit instruction); this table
only prepares the schema so a real `IntegrationAdapter` (Fase 2+) has
somewhere to persist its settings. `config` must never hold a secret in
plain text once an adapter is implemented — see `docs/SECURITY.md`
(hardening phase) for the encryption-at-rest plan.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin
from app.models.types import bigint_pk


class IntegrationConfig(Base, TimestampMixin, TenantMixin):
    """A tenant's configuration for one external integration type."""

    __tablename__ = "integration_configs"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="INACTIVE", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<IntegrationConfig id={self.id} type={self.integration_type!r}>"
