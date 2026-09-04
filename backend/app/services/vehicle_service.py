"""Vehicle service — business rules for veículos (seção 9), including the
plan-limit enforcement the spec requires on every creation (seção 6).
"""
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models.carrier import Carrier
from app.models.driver import Driver
from app.models.enums import AuditAction
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.vehicle_type import VehicleType
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from app.services.audit_service import write_audit_log
from app.services.license_service import enforce_vehicle_limit


def _as_dict(vehicle: Vehicle) -> dict:
    return {
        "plate": vehicle.plate, "brand": vehicle.brand, "model": vehicle.model, "carrier_id": vehicle.carrier_id,
        "status": vehicle.status.value if hasattr(vehicle.status, "value") else vehicle.status,
    }


def _validate_references(
    db: Session, tenant_id: int, *, vehicle_type_id: int | None, carrier_id: int | None, driver_id: int | None,
) -> None:
    checks = [
        (vehicle_type_id, VehicleType, "Tipo de veículo informado não existe ou não pertence à sua empresa."),
        (carrier_id, Carrier, "Transportadora informada não existe ou não pertence à sua empresa."),
        (driver_id, Driver, "Motorista informado não existe ou não pertence à sua empresa."),
    ]
    for record_id, model, message in checks:
        if record_id is None:
            continue
        instance = db.get(model, record_id)
        if instance is None or instance.tenant_id != tenant_id:
            raise ValidationFailedError(message)


def list_vehicles(
    db: Session, tenant_id: int, *, query: str | None, status: str | None, carrier_id: int | None,
    limit: int, offset: int,
) -> tuple[list[Vehicle], int]:
    return VehicleRepository(db, tenant_id).search(
        query=query, status=status, carrier_id=carrier_id, limit=limit, offset=offset,
    )


def get_vehicle(db: Session, tenant_id: int, vehicle_id: int) -> Vehicle:
    vehicle = VehicleRepository(db, tenant_id).get(vehicle_id)
    if vehicle is None:
        raise NotFoundError("Veículo não encontrado.")
    return vehicle


def create_vehicle(
    db: Session, tenant_id: int, actor: User, payload: VehicleCreate, ip_address: str | None,
) -> Vehicle:
    repo = VehicleRepository(db, tenant_id)
    if repo.get_by_plate(payload.plate) is not None:
        raise ConflictError("Já existe um veículo cadastrado com esta placa.")
    _validate_references(
        db, tenant_id, vehicle_type_id=payload.vehicle_type_id, carrier_id=payload.carrier_id,
        driver_id=payload.current_driver_id,
    )
    enforce_vehicle_limit(db, tenant_id)

    vehicle = Vehicle(
        tenant_id=tenant_id, plate=payload.plate, renavam=payload.renavam, vehicle_type_id=payload.vehicle_type_id,
        brand=payload.brand, model=payload.model, year=payload.year, carrier_id=payload.carrier_id,
        capacity=payload.capacity, current_driver_id=payload.current_driver_id, notes=payload.notes,
        created_by=actor.id, updated_by=actor.id,
    )
    repo.add(vehicle)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.CREATE, table_name="vehicles",
        record_id=str(vehicle.id), ip_address=ip_address, new_value=_as_dict(vehicle),
    )
    db.commit()
    db.refresh(vehicle)
    return vehicle


def update_vehicle(
    db: Session, tenant_id: int, actor: User, vehicle_id: int, payload: VehicleUpdate, ip_address: str | None,
) -> Vehicle:
    repo = VehicleRepository(db, tenant_id)
    vehicle = get_vehicle(db, tenant_id, vehicle_id)
    old_value = _as_dict(vehicle)

    if payload.plate and payload.plate != vehicle.plate:
        existing = repo.get_by_plate(payload.plate)
        if existing is not None and existing.id != vehicle.id:
            raise ConflictError("Já existe um veículo cadastrado com esta placa.")

    fields = payload.model_dump(exclude_unset=True)
    _validate_references(
        db, tenant_id,
        vehicle_type_id=fields.get("vehicle_type_id", vehicle.vehicle_type_id),
        carrier_id=fields.get("carrier_id", vehicle.carrier_id),
        driver_id=fields.get("current_driver_id", vehicle.current_driver_id),
    )

    for field, value in fields.items():
        setattr(vehicle, field, value)
    vehicle.updated_by = actor.id
    db.flush()

    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.UPDATE, table_name="vehicles",
        record_id=str(vehicle.id), ip_address=ip_address, old_value=old_value, new_value=_as_dict(vehicle),
    )
    db.commit()
    db.refresh(vehicle)
    return vehicle


def delete_vehicle(db: Session, tenant_id: int, actor: User, vehicle_id: int, ip_address: str | None) -> None:
    repo = VehicleRepository(db, tenant_id)
    vehicle = get_vehicle(db, tenant_id, vehicle_id)
    old_value = _as_dict(vehicle)
    repo.soft_delete(vehicle)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.DELETE, table_name="vehicles",
        record_id=str(vehicle_id), ip_address=ip_address, old_value=old_value,
    )
    db.commit()
