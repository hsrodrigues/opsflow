"""Product (produto/carga) model — the catalog of what actually gets
transported. Existed before only as free text (`ScheduleItem.
cargo_description`), which is why `ScheduleItem.quantity` was a bare number
with no unit declared anywhere in the UI: this fixes that at the root — a
programação that references a product shows that product's own
`unit_of_measure` next to the quantity field instead of a guess.
"""
from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.enums import ProductStatus, UnitOfMeasure
from app.models.types import bigint_pk, enum_column


class Product(Base, TimestampMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    unit_of_measure: Mapped[UnitOfMeasure] = mapped_column(
        enum_column(UnitOfMeasure, length=20), default=UnitOfMeasure.UNIDADE, nullable=False
    )
    default_weight_kg: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    status: Mapped[ProductStatus] = mapped_column(
        enum_column(ProductStatus, length=20), default=ProductStatus.ATIVO, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Product id={self.id} name={self.name!r}>"
