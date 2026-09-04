"""Vehicle repository (seção 9)."""
from sqlalchemy import func, or_, select

from app.models.vehicle import Vehicle
from app.repositories.base import TenantRepository


class VehicleRepository(TenantRepository[Vehicle]):
    model = Vehicle

    def search(
        self, *, query: str | None = None, status: str | None = None, carrier_id: int | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[Vehicle], int]:
        stmt = self._base_query()
        if query:
            like = f"%{query}%"
            stmt = stmt.where(or_(Vehicle.plate.ilike(like), Vehicle.brand.ilike(like), Vehicle.model.ilike(like)))
        if status:
            stmt = stmt.where(Vehicle.status == status)
        if carrier_id:
            stmt = stmt.where(Vehicle.carrier_id == carrier_id)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items_stmt = stmt.order_by(Vehicle.plate).limit(limit).offset(offset)
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total

    def get_by_plate(self, plate: str) -> Vehicle | None:
        return self.db.execute(self._base_query().where(Vehicle.plate == plate)).scalar_one_or_none()
