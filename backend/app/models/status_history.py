"""Status history — the operational timeline shown in the UI (seção 13)."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin
from app.models.enums import ScheduleStatus
from app.models.types import bigint_pk, enum_column


class StatusHistory(Base, TenantMixin):
    """One status transition recorded against an `Operation`."""

    __tablename__ = "status_history"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    operation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_status: Mapped[ScheduleStatus | None] = mapped_column(
        enum_column(ScheduleStatus, length=20), nullable=True
    )
    new_status: Mapped[ScheduleStatus] = mapped_column(enum_column(ScheduleStatus, length=20), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    operation: Mapped["Operation"] = relationship(back_populates="status_history")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<StatusHistory id={self.id} operation_id={self.operation_id} new_status={self.new_status}>"
