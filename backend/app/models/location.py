"""Location model — reusable origin/destination points for routes (seção 12/22).

Carries optional latitude/longitude so a future map integration (seção 22)
can be added without any schema change.
"""
from sqlalchemy import BigInteger, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin
from app.models.types import bigint_pk


class Location(Base, TimestampMixin, TenantMixin):
    """A named point (origin or destination) a `Route` can reference."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Location id={self.id} name={self.name!r}>"
