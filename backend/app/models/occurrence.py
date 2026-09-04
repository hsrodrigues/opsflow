"""Occurrence model (seção 14)."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.enums import OccurrenceSeverity, OccurrenceStatus
from app.models.types import bigint_pk, enum_column


class Occurrence(Base, TimestampMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """An operational incident, optionally linked to an operation/vehicle/driver."""

    __tablename__ = "occurrences"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    occurrence_type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("occurrence_types.id"), nullable=False
    )
    operation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("operations.id"), nullable=True)
    vehicle_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("vehicles.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("drivers.id"), nullable=True)
    responsible_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[OccurrenceSeverity] = mapped_column(
        enum_column(OccurrenceSeverity, length=20), default=OccurrenceSeverity.BAIXA, nullable=False
    )
    status: Mapped[OccurrenceStatus] = mapped_column(
        enum_column(OccurrenceStatus, length=20), default=OccurrenceStatus.ABERTA, nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    occurrence_type: Mapped["OccurrenceType"] = relationship()
    vehicle: Mapped["Vehicle"] = relationship()
    driver: Mapped["Driver"] = relationship()
    responsible_user: Mapped["User"] = relationship(foreign_keys=[responsible_user_id])
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="occurrence")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Occurrence id={self.id} severity={self.severity} status={self.status}>"
