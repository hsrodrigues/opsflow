"""Operation service — read model for the Centro de Operações (seção 21)."""
from datetime import date

from sqlalchemy.orm import Session

from app.models.operation import Operation
from app.repositories.operation_repository import OperationRepository
from app.schemas.operation import OperationOut, OperationsSummary


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
