"""Vehicle model (seção 9)."""
from sqlalchemy import BigInteger, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.enums import VehicleStatus
from app.models.types import bigint_pk, enum_column


class Vehicle(Base, TimestampMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """A vehicle available for operations, optionally tied to a carrier/driver."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    plate: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    renavam: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vehicle_type_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("vehicle_types.id"), nullable=True
    )
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    carrier_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("carriers.id"), nullable=True)
    capacity: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[VehicleStatus] = mapped_column(
        enum_column(VehicleStatus, length=20), default=VehicleStatus.DISPONIVEL, nullable=False
    )
    current_driver_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("drivers.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    vehicle_type: Mapped["VehicleType"] = relationship()
    carrier: Mapped["Carrier"] = relationship(back_populates="vehicles")
    current_driver: Mapped["Driver"] = relationship(foreign_keys=[current_driver_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Vehicle id={self.id} plate={self.plate!r}>"
