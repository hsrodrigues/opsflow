"""Carrier (transportadora) model (seção 11)."""
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.enums import CarrierStatus
from app.models.types import bigint_pk, enum_column


class Carrier(Base, TimestampMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """A transport company that operates vehicles/drivers for a tenant."""

    __tablename__ = "carriers"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(18), nullable=True, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CarrierStatus] = mapped_column(
        enum_column(CarrierStatus, length=20), default=CarrierStatus.ATIVO, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="carrier")
    drivers: Mapped[list["Driver"]] = relationship(back_populates="carrier")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Carrier id={self.id} legal_name={self.legal_name!r}>"
