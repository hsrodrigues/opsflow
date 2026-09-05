"""Schedule (programação) models (seção 13).

`Schedule` is a lightweight header grouping the day's items by shift;
`ScheduleItem` is one planned trip (rota, transportadora, veículo, motorista,
horário previsto, carga, quantidade). When an item leaves `PROGRAMADO` it
gets a corresponding `Operation` (see `operation.py`) that tracks real-time
execution — this keeps "what was planned" and "what is actually happening"
as separate, independently queryable concerns.
"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.enums import ScheduleStatus
from app.models.types import bigint_pk, enum_column


class Schedule(Base, TimestampMixin, TenantMixin, AuditMixin):
    """A header grouping schedule items for one date + shift (turno)."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift: Mapped[str] = mapped_column(String(20), nullable=False)  # ex.: MANHA, TARDE, NOITE
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    items: Mapped[list["ScheduleItem"]] = relationship(back_populates="schedule")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Schedule id={self.id} date={self.schedule_date} shift={self.shift}>"


class ScheduleItem(Base, TimestampMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """One planned trip within a `Schedule` (seção 13)."""

    __tablename__ = "schedule_items"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("routes.id"), nullable=False)
    carrier_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("carriers.id"), nullable=True)
    vehicle_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("vehicles.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("drivers.id"), nullable=True)
    # `SET NULL` (não `CASCADE`): apagar um produto do catálogo não pode
    # apagar o histórico de uma programação/operação já executada.
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False)
    cargo_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[ScheduleStatus] = mapped_column(
        enum_column(ScheduleStatus, length=20), default=ScheduleStatus.PROGRAMADO, nullable=False
    )

    schedule: Mapped["Schedule"] = relationship(back_populates="items")
    route: Mapped["Route"] = relationship()
    carrier: Mapped["Carrier"] = relationship()
    vehicle: Mapped["Vehicle"] = relationship()
    driver: Mapped["Driver"] = relationship()
    product: Mapped["Product"] = relationship()
    operation: Mapped["Operation"] = relationship(back_populates="schedule_item", uselist=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ScheduleItem id={self.id} status={self.status}>"
