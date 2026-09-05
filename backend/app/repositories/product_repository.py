"""Product repository."""
from sqlalchemy import func, or_, select

from app.models.product import Product
from app.repositories.base import TenantRepository


class ProductRepository(TenantRepository[Product]):
    model = Product

    def search(
        self, *, query: str | None = None, status: str | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[Product], int]:
        stmt = self._base_query()
        if query:
            like = f"%{query}%"
            stmt = stmt.where(or_(Product.name.ilike(like), Product.sku.ilike(like)))
        if status:
            stmt = stmt.where(Product.status == status)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items_stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total
