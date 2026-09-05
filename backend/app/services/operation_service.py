"""Operation service — read model for the Centro de Operações (seção 21)."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.enums import ScheduleStatus
from app.models.operation import Operation
from app.models.schedule import ScheduleItem
from app.repositories.operation_repository import OperationRepository
from app.schemas.operation import OperationOut, OperationsSummary
from app.services import schedule_service

_STALE_STATUSES = (ScheduleStatus.AGUARDANDO, ScheduleStatus.EM_FILA, ScheduleStatus.EM_OPERACAO)


def operation_to_out(operation: Operation) -> OperationOut:
    item = operation.schedule_item
    return OperationOut(
        id=operation.id, operation_number=operation.operation_number, schedule_item_id=item.id,
        route_name=item.route.name, vehicle_plate=item.vehicle.plate if item.vehicle else None,
        carrier_name=item.carrier.legal_name if item.carrier else None,
        driver_name=item.driver.full_name if item.driver else None,
        status=operation.status, scheduled_at=item.scheduled_at, arrived_at=operation.arrived_at,
        started_at=operation.started_at, completed_at=operation.completed_at,
    )


def list_active_operations(db: Session, tenant_id: int) -> list[Operation]:
    return OperationRepository(db, tenant_id).list_active()


def get_summary(db: Session, tenant_id: int, schedule_date: date) -> OperationsSummary:
    counts = OperationRepository(db, tenant_id).summary_for_date(schedule_date)
    return OperationsSummary(**counts)


def close_stale_operations(db: Session, tenant_id: int, stale_after_hours: int) -> list[int]:
    """Fecha (CANCELADO) operações penduradas há mais de `stale_after_hours`
    num status intermediário (AGUARDANDO/EM_FILA/EM_OPERACAO) sem ninguém
    ter mexido — pedido explícito do cliente ("fechamento automático de
    pendências"). Retorna os `schedule_item_id`s fechados, pra quem chamou
    poder notificar a respeito (ver `app/jobs/stale_operations_job.py`).

    Em MySQL, delega pra `sp_close_stale_operations` (uma viagem ao banco,
    atômica). Em qualquer outro dialeto (SQLite dos testes), reaproveita
    `schedule_service.change_status` — a MESMA função usada pelo robô de
    detecção de atraso e pela troca de status manual — item por item, o que
    garante que o fallback nunca diverge silenciosamente da regra "real" de
    transição de status (arrived_at/started_at/completed_at, StatusHistory,
    auditoria) só porque está rodando num banco diferente.
    """
    if db.get_bind().dialect.name == "mysql":
        result = db.execute(
            text("CALL sp_close_stale_operations(:tenant_id, :stale_after_hours)"),
            {"tenant_id": tenant_id, "stale_after_hours": stale_after_hours},
        )
        rows = result.fetchall()
        result.close()
        item_ids = [int(row.schedule_item_id) for row in rows]
        db.commit()
        return item_ids

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=stale_after_hours)
    stale_items = db.execute(
        select(ScheduleItem)
        .join(Operation, Operation.schedule_item_id == ScheduleItem.id)
        .where(
            ScheduleItem.tenant_id == tenant_id, Operation.status.in_(_STALE_STATUSES),
            Operation.updated_at < cutoff,
        )
    ).scalars().all()

    note = f"Fechado automaticamente por rotina de limpeza — sem atualização há mais de {stale_after_hours} hora(s)."
    item_ids = []
    for item in stale_items:
        schedule_service.change_status(db, tenant_id, None, item.id, ScheduleStatus.CANCELADO, note, ip_address=None)
        item_ids.append(item.id)
    return item_ids
