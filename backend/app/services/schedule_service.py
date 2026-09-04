"""Schedule service — business rules for programação operacional (seção 13).

`change_status` is the one function that turns a `ScheduleItem` into a live
`Operation`: the first call that moves a item away from `PROGRAMADO` creates
the `Operation` row (and its `operation_number`); every call after that just
advances the same `Operation` and appends a `StatusHistory` row — the
timeline shown in the UI.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.carrier import Carrier
from app.models.driver import Driver
from app.models.enums import AuditAction, ScheduleStatus
from app.models.operation import Operation
from app.models.route import Route
from app.models.schedule import ScheduleItem
from app.models.status_history import StatusHistory
from app.models.user import User
from app.models.vehicle import Vehicle
from app.repositories.schedule_repository import ScheduleItemRepository, ScheduleRepository
from app.schemas.schedule import ScheduleItemCreate, ScheduleItemOut, ScheduleItemUpdate, StatusHistoryOut
from app.services.audit_service import write_audit_log


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def schedule_item_to_out(item: ScheduleItem) -> ScheduleItemOut:
    return ScheduleItemOut(
        id=item.id, schedule_date=item.schedule.schedule_date, shift=item.schedule.shift,
        route_name=item.route.name, carrier_name=item.carrier.legal_name if item.carrier else None,
        vehicle_plate=item.vehicle.plate if item.vehicle else None,
        driver_name=item.driver.full_name if item.driver else None,
        scheduled_at=item.scheduled_at, cargo_description=item.cargo_description, quantity=item.quantity,
        notes=item.notes, status=item.status,
        operation_number=item.operation.operation_number if item.operation else None,
    )


def _validate_references(
    db: Session, tenant_id: int, *, route_id: int | None, carrier_id: int | None, vehicle_id: int | None,
    driver_id: int | None,
) -> None:
    checks = [
        (route_id, Route, "Rota informada não existe ou não pertence à sua empresa."),
        (carrier_id, Carrier, "Transportadora informada não existe ou não pertence à sua empresa."),
        (vehicle_id, Vehicle, "Veículo informado não existe ou não pertence à sua empresa."),
        (driver_id, Driver, "Motorista informado não existe ou não pertence à sua empresa."),
    ]
    for record_id, model, message in checks:
        if record_id is None:
            continue
        instance = db.get(model, record_id)
        if instance is None or instance.tenant_id != tenant_id:
            raise ValidationFailedError(message)


def list_schedule_items(
    db: Session, tenant_id: int, *, schedule_date, status: str | None, limit: int, offset: int,
) -> tuple[list[ScheduleItem], int]:
    return ScheduleItemRepository(db, tenant_id).search(
        schedule_date=schedule_date, status=status, limit=limit, offset=offset,
    )


def get_schedule_item(db: Session, tenant_id: int, item_id: int) -> ScheduleItem:
    item = ScheduleItemRepository(db, tenant_id).get(item_id)
    if item is None:
        raise NotFoundError("Programação não encontrada.")
    return item


def create_schedule_item(
    db: Session, tenant_id: int, actor: User, payload: ScheduleItemCreate, ip_address: str | None,
) -> ScheduleItem:
    _validate_references(
        db, tenant_id, route_id=payload.route_id, carrier_id=payload.carrier_id,
        vehicle_id=payload.vehicle_id, driver_id=payload.driver_id,
    )
    schedule = ScheduleRepository(db, tenant_id).get_or_create(payload.schedule_date, payload.shift)

    item = ScheduleItem(
        tenant_id=tenant_id, schedule_id=schedule.id, route_id=payload.route_id, carrier_id=payload.carrier_id,
        vehicle_id=payload.vehicle_id, driver_id=payload.driver_id, scheduled_at=payload.scheduled_at,
        cargo_description=payload.cargo_description, quantity=payload.quantity, notes=payload.notes,
        created_by=actor.id, updated_by=actor.id,
    )
    ScheduleItemRepository(db, tenant_id).add(item)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.CREATE, table_name="schedule_items",
        record_id=str(item.id), ip_address=ip_address,
    )
    db.commit()
    db.refresh(item)
    return item


def update_schedule_item(
    db: Session, tenant_id: int, actor: User, item_id: int, payload: ScheduleItemUpdate, ip_address: str | None,
) -> ScheduleItem:
    item = get_schedule_item(db, tenant_id, item_id)
    fields = payload.model_dump(exclude_unset=True)
    _validate_references(
        db, tenant_id,
        route_id=fields.get("route_id", item.route_id), carrier_id=fields.get("carrier_id", item.carrier_id),
        vehicle_id=fields.get("vehicle_id", item.vehicle_id), driver_id=fields.get("driver_id", item.driver_id),
    )
    for field, value in fields.items():
        setattr(item, field, value)
    item.updated_by = actor.id
    db.flush()

    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.UPDATE, table_name="schedule_items",
        record_id=str(item.id), ip_address=ip_address,
    )
    db.commit()
    db.refresh(item)
    return item


def change_status(
    db: Session, tenant_id: int, actor: User, item_id: int, new_status: ScheduleStatus, notes: str | None,
    ip_address: str | None,
) -> ScheduleItem:
    item = get_schedule_item(db, tenant_id, item_id)
    previous_status = item.status
    now = _utc_now()

    item.status = new_status
    item.updated_by = actor.id

    operation = item.operation
    if operation is None:
        operation = Operation(
            tenant_id=tenant_id, schedule_item_id=item.id, operation_number="", status=new_status,
            created_by=actor.id, updated_by=actor.id,
        )
        db.add(operation)
        db.flush()
        operation.operation_number = str(10_000 + operation.id)
        item.operation = operation
    else:
        operation.status = new_status
        operation.updated_by = actor.id

    if new_status in (ScheduleStatus.AGUARDANDO, ScheduleStatus.EM_FILA) and operation.arrived_at is None:
        operation.arrived_at = now
    if new_status == ScheduleStatus.EM_OPERACAO and operation.started_at is None:
        operation.started_at = now
    if new_status == ScheduleStatus.CONCLUIDO:
        operation.completed_at = now
    db.flush()

    db.add(
        StatusHistory(
            tenant_id=tenant_id, operation_id=operation.id, previous_status=previous_status, new_status=new_status,
            changed_by=actor.id, changed_at=now, notes=notes,
        )
    )
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.STATUS_CHANGE, table_name="schedule_items",
        record_id=str(item.id), ip_address=ip_address,
        old_value={"status": previous_status.value}, new_value={"status": new_status.value},
    )
    db.commit()
    db.refresh(item)
    return item


def get_status_history(db: Session, tenant_id: int, item_id: int) -> list[StatusHistoryOut]:
    item = get_schedule_item(db, tenant_id, item_id)
    if item.operation is None:
        return []
    return [
        StatusHistoryOut(
            previous_status=entry.previous_status, new_status=entry.new_status,
            changed_at=entry.changed_at, notes=entry.notes,
        )
        for entry in item.operation.status_history
    ]
