"""Occurrence repository (seção 14)."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.occurrence import Occurrence
from app.repositories.base import TenantRepository


class OccurrenceRepository(TenantRepository[Occurrence]):
    model = Occurrence

    def _base_query(self):
        return super()._base_query().options(
            selectinload(Occurrence.occurrence_type), selectinload(Occurrence.vehicle),
            selectinload(Occurrence.driver), selectinload(Occurrence.responsible_user),
        )

    def search(
        self, *, severity: str | None = None, status: str | None = None, start_date: date | None = None,
        end_date: date | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[Occurrence], int]:
        stmt = self._base_query()
        if severity:
            stmt = stmt.where(Occurrence.severity == severity)
        if status:
            stmt = stmt.where(Occurrence.status == status)
        if start_date:
            stmt = stmt.where(Occurrence.occurred_at >= start_date)
        if end_date:
            stmt = stmt.where(Occurrence.occurred_at < end_date)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items_stmt = stmt.order_by(Occurrence.occurred_at.desc()).limit(limit).offset(offset)
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total
