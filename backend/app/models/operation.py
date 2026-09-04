"""Operation model — the real-time execution instance of a schedule item.

Created once a `ScheduleItem` leaves `PROGRAMADO`. Powers the Centro de
Operações screen (seção 21) and accumulates a `StatusHistory` timeline
(seção 13) as it moves through its lifecycle.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, TenantMixin, TimestampMixin
from app.models.enums import ScheduleStatus
from app.models.types import bigint_pk, enum_column


class Operation(Base, TimestampMixin, TenantMixin, AuditMixin):
    """The live execution record of one `ScheduleItem`."""

    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    schedule_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("schedule_items.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # Código curto e amigável exibido nas telas (ex.: "10231") — gerado pelo
    # service layer, sequencial por tenant.
    operation_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[ScheduleStatus] = mapped_column(
        enum_column(ScheduleStatus, length=20), default=ScheduleStatus.AGUARDANDO, nullable=False
    )
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    schedule_item: Mapped["ScheduleItem"] = relationship(back_populates="operation")
    status_history: Mapped[list["StatusHistory"]] = relationship(
        back_populates="operation", order_by="StatusHistory.changed_at"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Operation id={self.id} number={self.operation_number!r} status={self.status}>"
