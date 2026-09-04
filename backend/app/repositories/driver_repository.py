"""Driver repository (seção 10)."""
from datetime import date, timedelta

from sqlalchemy import func, or_, select

from app.models.driver import Driver
from app.repositories.base import TenantRepository


class DriverRepository(TenantRepository[Driver]):
    model = Driver

    def search(
        self, *, query: str | None = None, status: str | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[Driver], int]:
        stmt = self._base_query()
        if query:
            like = f"%{query}%"
            stmt = stmt.where(or_(Driver.full_name.ilike(like), Driver.cpf.ilike(like)))
        if status:
            stmt = stmt.where(Driver.status == status)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items_stmt = stmt.order_by(Driver.full_name).limit(limit).offset(offset)
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total

    def get_by_cpf(self, cpf: str) -> Driver | None:
        return self.db.execute(self._base_query().where(Driver.cpf == cpf)).scalar_one_or_none()

    def expiring_cnh(self, *, within_days: int = 30) -> list[Driver]:
        """Drivers whose CNH expires within `within_days` (seção 10: alerta de vencimento)."""
        deadline = date.today() + timedelta(days=within_days)
        stmt = self._base_query().where(Driver.cnh_expiry.is_not(None), Driver.cnh_expiry <= deadline)
        return list(self.db.execute(stmt.order_by(Driver.cnh_expiry)).scalars().all())
