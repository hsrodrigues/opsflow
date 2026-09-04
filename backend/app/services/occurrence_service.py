"""Occurrence service — business rules for ocorrências (seção 14)."""
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.driver import Driver
from app.models.enums import AuditAction
from app.models.occurrence import Occurrence
from app.models.user import User
from app.models.vehicle import Vehicle
from app.repositories.occurrence_repository import OccurrenceRepository
from app.repositories.occurrence_type_repository import get_or_create_occurrence_type
from app.schemas.occurrence import OccurrenceCreate, OccurrenceOut, OccurrenceUpdate
from app.services.audit_service import write_audit_log


def occurrence_to_out(occurrence: Occurrence) -> OccurrenceOut:
    return OccurrenceOut(
        id=occurrence.id, occurrence_type_name=occurrence.occurrence_type.name,
        vehicle_plate=occurrence.vehicle.plate if occurrence.vehicle else None,
        driver_name=occurrence.driver.full_name if occurrence.driver else None,
        responsible_user_name=occurrence.responsible_user.full_name if occurrence.responsible_user else None,
        description=occurrence.description, severity=occurrence.severity, status=occurrence.status,
        occurred_at=occurrence.occurred_at,
    )


def _validate_references(db: Session, tenant_id: int, *, vehicle_id: int | None, driver_id: int | None) -> None:
    checks = [
        (vehicle_id, Vehicle, "Veículo informado não existe ou não pertence à sua empresa."),
        (driver_id, Driver, "Motorista informado não existe ou não pertence à sua empresa."),
    ]
    for record_id, model, message in checks:
        if record_id is None:
            continue
        instance = db.get(model, record_id)
        if instance is None or instance.tenant_id != tenant_id:
            raise ValidationFailedError(message)


def list_occurrences(
    db: Session, tenant_id: int, *, severity: str | None, status: str | None, start_date, end_date,
    limit: int, offset: int,
) -> tuple[list[Occurrence], int]:
    return OccurrenceRepository(db, tenant_id).search(
        severity=severity, status=status, start_date=start_date, end_date=end_date, limit=limit, offset=offset,
    )


def get_occurrence(db: Session, tenant_id: int, occurrence_id: int) -> Occurrence:
    occurrence = OccurrenceRepository(db, tenant_id).get(occurrence_id)
    if occurrence is None:
        raise NotFoundError("Ocorrência não encontrada.")
    return occurrence


def create_occurrence(
    db: Session, tenant_id: int, actor: User, payload: OccurrenceCreate, ip_address: str | None,
) -> Occurrence:
    _validate_references(db, tenant_id, vehicle_id=payload.vehicle_id, driver_id=payload.driver_id)
    occurrence_type = get_or_create_occurrence_type(db, tenant_id, payload.occurrence_type_name)

    occurrence = Occurrence(
        tenant_id=tenant_id, occurrence_type_id=occurrence_type.id, vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id, responsible_user_id=actor.id, description=payload.description,
        severity=payload.severity, occurred_at=payload.occurred_at, created_by=actor.id, updated_by=actor.id,
    )
    OccurrenceRepository(db, tenant_id).add(occurrence)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.CREATE, table_name="occurrences",
        record_id=str(occurrence.id), ip_address=ip_address,
    )
    db.commit()
    db.refresh(occurrence)
    return occurrence


def update_occurrence(
    db: Session, tenant_id: int, actor: User, occurrence_id: int, payload: OccurrenceUpdate, ip_address: str | None,
) -> Occurrence:
    occurrence = get_occurrence(db, tenant_id, occurrence_id)
    fields = payload.model_dump(exclude_unset=True, exclude={"occurrence_type_name"})
    _validate_references(
        db, tenant_id, vehicle_id=fields.get("vehicle_id", occurrence.vehicle_id),
        driver_id=fields.get("driver_id", occurrence.driver_id),
    )
    for field, value in fields.items():
        setattr(occurrence, field, value)
    if payload.occurrence_type_name is not None:
        occurrence_type = get_or_create_occurrence_type(db, tenant_id, payload.occurrence_type_name)
        occurrence.occurrence_type = occurrence_type
        occurrence.occurrence_type_id = occurrence_type.id
    occurrence.updated_by = actor.id
    db.flush()

    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.UPDATE, table_name="occurrences",
        record_id=str(occurrence.id), ip_address=ip_address,
    )
    db.commit()
    db.refresh(occurrence)
    return occurrence
