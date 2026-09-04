"""Occurrence type — tenant-configurable occurrence classification (seção 14)."""
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin
from app.models.types import bigint_pk


class OccurrenceType(Base, TimestampMixin, TenantMixin):
    """A tenant-defined occurrence category (atraso, quebra, acidente, ...)."""

    __tablename__ = "occurrence_types"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<OccurrenceType id={self.id} name={self.name!r}>"
