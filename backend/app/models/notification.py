"""Notification model (seção 20)."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin
from app.models.enums import NotificationSeverity
from app.models.types import bigint_pk, enum_column


class Notification(Base, TimestampMixin, TenantMixin):
    """An in-app notification. `user_id=None` means it is a tenant-wide broadcast."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[NotificationSeverity] = mapped_column(
        enum_column(NotificationSeverity, length=20), default=NotificationSeverity.INFO, nullable=False
    )
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Notification id={self.id} severity={self.severity}>"
