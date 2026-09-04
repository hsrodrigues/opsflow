"""Carrier repository (seção 11)."""
from sqlalchemy import func, or_, select

from app.models.carrier import Carrier
from app.repositories.base import TenantRepository


class CarrierRepository(TenantRepository[Carrier]):
    model = Carrier

    def search(
        self, *, query: str | None = None, status: str | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[Carrier], int]:
        stmt = self._base_query()
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(Carrier.legal_name.ilike(like), Carrier.trade_name.ilike(like), Carrier.cnpj.ilike(like))
            )
        if status:
            stmt = stmt.where(Carrier.status == status)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items_stmt = stmt.order_by(Carrier.legal_name).limit(limit).offset(offset)
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total

    def get_by_cnpj(self, cnpj: str) -> Carrier | None:
        return self.db.execute(self._base_query().where(Carrier.cnpj == cnpj)).scalar_one_or_none()
