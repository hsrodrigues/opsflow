"""Route model (seção 12)."""
from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.enums import RouteStatus
from app.models.types import bigint_pk, enum_column


class Route(Base, TimestampMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """A named origin→destination route usable by schedule items."""

    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    origin_location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id"), nullable=False)
    destination_location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id"), nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    estimated_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operation_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[RouteStatus] = mapped_column(
        enum_column(RouteStatus, length=20), default=RouteStatus.ATIVA, nullable=False
    )

    origin: Mapped["Location"] = relationship(foreign_keys=[origin_location_id])
    destination: Mapped["Location"] = relationship(foreign_keys=[destination_location_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Route id={self.id} name={self.name!r}>"
