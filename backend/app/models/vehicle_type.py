"""Vehicle type — a tenant-configurable classification for vehicles."""
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin
from app.models.types import bigint_pk


class VehicleType(Base, TimestampMixin, TenantMixin):
    """A tenant-defined vehicle classification (e.g. "Caminhão Truck")."""

    __tablename__ = "vehicle_types"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<VehicleType id={self.id} name={self.name!r}>"
