"""Subscription plan catalog (STARTER / PROFESSIONAL / BUSINESS / ENTERPRISE).

Plans are global reference data (not tenant-scoped) so that limits and
features can be reconfigured for all customers on a given plan without a
redeploy — see seção 7 do documento de especificação.
"""
from sqlalchemy import BigInteger, Boolean, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PlanCode
from app.models.types import bigint_pk, enum_column


class Plan(Base, TimestampMixin):
    """A billing/feature tier that a tenant's license can be attached to."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    code: Mapped[PlanCode] = mapped_column(enum_column(PlanCode, length=20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = ilimitado
    max_vehicles: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = ilimitado
    features: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")
    licenses: Mapped[list["License"]] = relationship(back_populates="plan")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Plan id={self.id} code={self.code}>"
