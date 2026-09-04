"""Schedule / ScheduleItem repositories (seção 13)."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.schedule import Schedule, ScheduleItem
from app.repositories.base import TenantRepository


class ScheduleRepository(TenantRepository[Schedule]):
    model = Schedule

    def get_or_create(self, schedule_date: date, shift: str) -> Schedule:
        stmt = self._base_query().where(Schedule.schedule_date == schedule_date, Schedule.shift == shift)
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return existing
        schedule = Schedule(tenant_id=self.tenant_id, schedule_date=schedule_date, shift=shift)
        return self.add(schedule)


class ScheduleItemRepository(TenantRepository[ScheduleItem]):
    model = ScheduleItem

    def _base_query(self):
        return super()._base_query().options(
            selectinload(ScheduleItem.schedule),
            selectinload(ScheduleItem.route),
            selectinload(ScheduleItem.carrier),
            selectinload(ScheduleItem.vehicle),
            selectinload(ScheduleItem.driver),
            selectinload(ScheduleItem.operation),
        )

    def search(
        self, *, schedule_date: date | None = None, status: str | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[ScheduleItem], int]:
        stmt = self._base_query()
        if schedule_date is not None:
            stmt = stmt.join(Schedule, ScheduleItem.schedule_id == Schedule.id).where(
                Schedule.schedule_date == schedule_date
            )
        if status:
            stmt = stmt.where(ScheduleItem.status == status)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items_stmt = stmt.order_by(ScheduleItem.scheduled_at).limit(limit).offset(offset)
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total
