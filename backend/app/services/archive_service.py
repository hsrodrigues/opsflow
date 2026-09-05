"""Archive service (seção 41 "Automações", pedido explícito do cliente:
"arquivamento de dados antigos... mantendo as tabelas principais leves
conforme o volume cresce"). Move operações/ocorrências antigas e já
concluídas pra fora das tabelas principais.

Ação de infraestrutura, cross-tenant por natureza na forma como é exposta
(`/api/v1/platform/archive`, atrás de `require_platform_admin` — mesma
lógica do backup: decidir QUANDO arquivar é uma decisão de quem opera a
plataforma, não algo silencioso rodando toda noite sem ninguém olhando,
diferente dos outros 4 robôs em `app/jobs/`), mas a função de serviço abaixo
roda por tenant, um de cada vez.
"""
import calendar
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationFailedError
from app.models.archive import OccurrenceArchive, OperationArchive, ScheduleItemArchive, StatusHistoryArchive
from app.models.enums import OccurrenceStatus, ScheduleStatus
from app.models.occurrence import Occurrence
from app.models.operation import Operation
from app.models.schedule import ScheduleItem
from app.models.status_history import StatusHistory
from app.models.tenant import Tenant


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _subtract_months(when: datetime, months: int) -> datetime:
    """Sem dependência externa (`python-dateutil` não é usado neste
    projeto): mesmo comportamento de `INTERVAL n MONTH` do MySQL, inclusive
    no caso de dia inexistente no mês de destino (31/mar - 1 mês -> 28 ou
    29/fev, nunca um erro `day is out of range`)."""
    total_months = when.year * 12 + (when.month - 1) - months
    year, month = divmod(total_months, 12)
    month += 1
    day = min(when.day, calendar.monthrange(year, month)[1])
    return when.replace(year=year, month=month, day=day)


def archive_old_records_all_tenants(db: Session, older_than_months: int) -> dict:
    """Varre todos os tenants (ativos ou não — arquivar dado antigo não deve
    depender da empresa ainda estar ativa) e soma os totais. Chamado pelo
    Console de Plataforma (`POST /api/v1/platform/archive`) — arquivar é uma
    ação cross-tenant por natureza (mantém as tabelas do sistema inteiro
    leves), então SUPER_ADMIN dispara pra todo mundo de uma vez, não
    tenant por tenant.
    """
    tenant_ids = [row[0] for row in db.execute(select(Tenant.id)).all()]
    totals = {"operations_archived": 0, "occurrences_archived": 0}
    for tenant_id in tenant_ids:
        result = archive_old_records(db, tenant_id, older_than_months)
        totals["operations_archived"] += result["operations_archived"]
        totals["occurrences_archived"] += result["occurrences_archived"]
    return totals


def archive_old_records(db: Session, tenant_id: int, older_than_months: int) -> dict:
    """Em MySQL, delega pra `sp_archive_old_records` (uma viagem ao banco,
    atômica). Em qualquer outro dialeto (SQLite dos testes), replica a
    MESMA regra via ORM — ver a stored procedure na migration `..._stored_
    procedures.py` pro corpo SQL espelhado aqui.
    """
    if older_than_months < 1:
        raise ValidationFailedError("older_than_months precisa ser pelo menos 1.")

    if db.get_bind().dialect.name == "mysql":
        result = db.execute(
            text("CALL sp_archive_old_records(:tenant_id, :months)"),
            {"tenant_id": tenant_id, "months": older_than_months},
        )
        row = result.fetchone()
        result.close()
        db.commit()
        return {"operations_archived": int(row[0]), "occurrences_archived": int(row[1])}

    return _archive_old_records_fallback(db, tenant_id, older_than_months)


def _archive_old_records_fallback(db: Session, tenant_id: int, older_than_months: int) -> dict:
    cutoff = _subtract_months(_utc_now(), older_than_months)
    archived_at = _utc_now()

    # --- operações concluídas/canceladas, sem ocorrência vinculada ---
    candidate_operations = db.execute(
        select(Operation).where(
            Operation.tenant_id == tenant_id,
            Operation.status.in_((ScheduleStatus.CONCLUIDO, ScheduleStatus.CANCELADO)),
            Operation.updated_at < cutoff,
        )
    ).scalars().all()

    linked_operation_ids = {
        row[0] for row in db.execute(
            select(Occurrence.operation_id).where(Occurrence.operation_id.is_not(None))
        ).all()
    }
    operations_to_archive = [op for op in candidate_operations if op.id not in linked_operation_ids]

    for operation in operations_to_archive:
        item = db.get(ScheduleItem, operation.schedule_item_id)
        history_rows = db.execute(
            select(StatusHistory).where(StatusHistory.operation_id == operation.id)
        ).scalars().all()

        db.add(OperationArchive(
            id=operation.id, tenant_id=operation.tenant_id, schedule_item_id=operation.schedule_item_id,
            operation_number=operation.operation_number, status=operation.status, arrived_at=operation.arrived_at,
            started_at=operation.started_at, completed_at=operation.completed_at, created_at=operation.created_at,
            updated_at=operation.updated_at, created_by=operation.created_by, updated_by=operation.updated_by,
            archived_at=archived_at,
        ))
        if item is not None:
            db.add(ScheduleItemArchive(
                id=item.id, tenant_id=item.tenant_id, schedule_id=item.schedule_id, route_id=item.route_id,
                carrier_id=item.carrier_id, vehicle_id=item.vehicle_id, driver_id=item.driver_id,
                product_id=item.product_id, scheduled_at=item.scheduled_at,
                cargo_description=item.cargo_description, quantity=item.quantity, notes=item.notes,
                status=item.status, created_at=item.created_at, updated_at=item.updated_at,
                created_by=item.created_by, updated_by=item.updated_by, deleted_at=item.deleted_at,
                archived_at=archived_at,
            ))
        for history in history_rows:
            db.add(StatusHistoryArchive(
                id=history.id, tenant_id=history.tenant_id, operation_id=history.operation_id,
                previous_status=history.previous_status, new_status=history.new_status,
                changed_by=history.changed_by, changed_at=history.changed_at, notes=history.notes,
                archived_at=archived_at,
            ))
        db.flush()
        # Ordem explícita (filhos antes dos pais) — o fallback não pode
        # contar com ON DELETE CASCADE: SQLite só aplica isso com
        # `PRAGMA foreign_keys=ON`, que este projeto não liga.
        for history in history_rows:
            db.delete(history)
        db.delete(operation)
        if item is not None:
            db.delete(item)

    # --- ocorrências resolvidas/canceladas, sem anexo ---
    candidate_occurrences = db.execute(
        select(Occurrence).where(
            Occurrence.tenant_id == tenant_id,
            Occurrence.status.in_((OccurrenceStatus.RESOLVIDA, OccurrenceStatus.CANCELADA)),
            Occurrence.created_at < cutoff, Occurrence.deleted_at.is_(None),
        )
    ).scalars().all()

    occurrences_archived = 0
    for occurrence in candidate_occurrences:
        if occurrence.attachments:
            continue
        db.add(OccurrenceArchive(
            id=occurrence.id, tenant_id=occurrence.tenant_id, occurrence_type_id=occurrence.occurrence_type_id,
            operation_id=occurrence.operation_id, vehicle_id=occurrence.vehicle_id,
            driver_id=occurrence.driver_id, responsible_user_id=occurrence.responsible_user_id,
            description=occurrence.description, severity=occurrence.severity, status=occurrence.status,
            occurred_at=occurrence.occurred_at, created_at=occurrence.created_at, updated_at=occurrence.updated_at,
            created_by=occurrence.created_by, updated_by=occurrence.updated_by, deleted_at=occurrence.deleted_at,
            archived_at=archived_at,
        ))
        db.flush()
        db.delete(occurrence)
        occurrences_archived += 1

    db.commit()
    return {"operations_archived": len(operations_to_archive), "occurrences_archived": occurrences_archived}
