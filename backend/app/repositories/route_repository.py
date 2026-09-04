"""Route repository (seção 12)."""
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.route import Route
from app.repositories.base import TenantRepository


class RouteRepository(TenantRepository[Route]):
    model = Route

    def _base_query(self):
        return super()._base_query().options(selectinload(Route.origin), selectinload(Route.destination))

    def search(
        self, *, query: str | None = None, status: str | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[Route], int]:
        # A busca cobre apenas Route.name (não os nomes de origem/destino
        # separadamente): a convenção de nomear a rota como "Origem →
        # Destino" (ver database/seeds/seed_demo.py) já torna isso
        # suficiente, sem precisar de um JOIN extra em locations.
        stmt = self._base_query()
        if query:
            stmt = stmt.where(Route.name.ilike(f"%{query}%"))
        if status:
            stmt = stmt.where(Route.status == status)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items_stmt = stmt.order_by(Route.name).limit(limit).offset(offset)
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total
