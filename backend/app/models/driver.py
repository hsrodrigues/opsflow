"""Driver (motorista) model (seção 10)."""
from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.enums import DriverStatus
from app.models.types import bigint_pk, enum_column


class Driver(Base, TimestampMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """A driver, optionally linked to a carrier. CNH expiry drives alerts (seção 10)."""

    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    cpf: Mapped[str] = mapped_column(String(14), nullable=False, index=True)
    cnh_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cnh_category: Mapped[str | None] = mapped_column(String(5), nullable=True)
    cnh_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    carrier_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("carriers.id"), nullable=True)
    status: Mapped[DriverStatus] = mapped_column(
        enum_column(DriverStatus, length=20), default=DriverStatus.ATIVO, nullable=False
    )

    carrier: Mapped["Carrier"] = relationship(back_populates="drivers")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Driver id={self.id} full_name={self.full_name!r}>"
