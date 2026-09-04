"""Subscription model — links a tenant to a plan over a billing period.

Kept distinct from `License` (see `license.py`): a `Subscription` is the
commercial/billing record (which plan, since when, current period), while a
`License` is the enforcement record the API validates on every login (status,
expiration, effective limits). This separation lets a future `PaymentProvider`
integration (seção 55) manage subscriptions without touching license
enforcement logic.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import bigint_pk


class Subscription(Base, TimestampMixin):
    """A tenant's subscription to a plan over a billing period."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Subscription id={self.id} tenant_id={self.tenant_id} plan_id={self.plan_id}>"
