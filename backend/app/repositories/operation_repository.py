"""Operation repository — powers the Centro de Operações (seção 21)."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.enums import ScheduleStatus
from app.models.operation import Operation
from app.models.schedule import Schedule, ScheduleItem
from app.repositories.base import TenantRepository

_INACTIVE_STATUSES = (ScheduleStatus.CONCLUIDO, ScheduleStatus.CANCELADO)


class OperationRepository(TenantRepository[Operation]):
    model = Operation

    def _base_query(self):
        return super()._base_query().options(
            selectinload(Operation.schedule_item).selectinload(ScheduleItem.route),
            selectinload(Operation.schedule_item).selectinload(ScheduleItem.vehicle),
            selectinload(Operation.schedule_item).selectinload(ScheduleItem.carrier),
            selectinload(Operation.schedule_item).selectinload(ScheduleItem.driver),
        )

    def list_active(self, *, limit: int = 200) -> list[Operation]:
        """Every operation not yet finished/cancelled — the live board."""
        stmt = self._base_query().where(Operation.status.not_in(_INACTIVE_STATUSES))
        stmt = stmt.order_by(Operation.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def summary_for_date(self, schedule_date: date) -> dict[str, int]:
        """Counters for the Centro de Operações header (seção 21)."""
        programadas_stmt = (
            select(func.count())
            .select_from(ScheduleItem)
            .join(Schedule, ScheduleItem.schedule_id == Schedule.id)
            .where(
                ScheduleItem.tenant_id == self.tenant_id,
                ScheduleItem.deleted_at.is_(None),
                Schedule.schedule_date == schedule_date,
                ScheduleItem.status == ScheduleStatus.PROGRAMADO,
            )
        )
        em_operacao_stmt = self._status_count_for_date(schedule_date, ScheduleStatus.EM_OPERACAO)
        atrasadas_stmt = self._status_count_for_date(schedule_date, ScheduleStatus.ATRASADO)

        return {
            "programadas": self.db.execute(programadas_stmt).scalar_one(),
            "em_operacao": self.db.execute(em_operacao_stmt).scalar_one(),
            "atrasadas": self.db.execute(atrasadas_stmt).scalar_one(),
        }

    def _status_count_for_date(self, schedule_date: date, status: ScheduleStatus):
        return (
            select(func.count())
            .select_from(Operation)
            .join(ScheduleItem, Operation.schedule_item_id == ScheduleItem.id)
            .join(Schedule, ScheduleItem.schedule_id == Schedule.id)
            .where(
                Operation.tenant_id == self.tenant_id,
                Schedule.schedule_date == schedule_date,
                Operation.status == status,
            )
        )
