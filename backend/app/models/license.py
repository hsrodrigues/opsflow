"""License model — the record the API validates on every login (seção 6).

`license_key` is a public identifier, never a secret: the actual validation
is always performed server-side against `status`/`expires_at`/limits, so a
copied key alone grants nothing without a valid, non-expired, ACTIVE/TRIAL
record on the server.

`tenant_id` is nullable to support self-activation: a `SUPER_ADMIN` can
generate a key with no company attached yet (`tenant_id IS NULL` *is* "not
activated" — there's no separate boolean for it), hand it to a prospective
customer, and the customer's own signup (`POST /api/v1/activation/activate`)
claims that same row by filling in `tenant_id` and the plan's actual dates —
never creating a second license record. `pending_trial_days`/`activated_at`
only matter for that unclaimed window.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import LicenseStatus
from app.models.types import bigint_pk, enum_column


class License(Base, TimestampMixin):
    """A tenant's commercial license, validated by the API on every login."""

    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plans.id"), nullable=False)
    license_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[LicenseStatus] = mapped_column(
        enum_column(LicenseStatus, length=20), default=LicenseStatus.TRIAL, nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Dias de teste concedidos só a partir da ATIVAÇÃO, não da geração da
    # chave (uma chave pode ficar semanas sem uso antes do cliente digitá-la
    # — começar a contar antes disso desperdiçaria o período de teste).
    pending_trial_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Overrides opcionais dos limites do plano (None = usa o limite do plano).
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_vehicles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="licenses")
    plan: Mapped["Plan"] = relationship(back_populates="licenses")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<License id={self.id} tenant_id={self.tenant_id} status={self.status}>"
