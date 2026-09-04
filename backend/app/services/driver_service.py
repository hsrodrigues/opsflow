"""Driver service — business rules for motoristas (seção 10)."""
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models.carrier import Carrier
from app.models.driver import Driver
from app.models.enums import AuditAction
from app.models.user import User
from app.repositories.driver_repository import DriverRepository
from app.schemas.driver import DriverCreate, DriverUpdate
from app.services.audit_service import write_audit_log


def _as_dict(driver: Driver) -> dict:
    return {
        "full_name": driver.full_name, "cpf": driver.cpf, "cnh_expiry": str(driver.cnh_expiry or ""),
        "carrier_id": driver.carrier_id,
        "status": driver.status.value if hasattr(driver.status, "value") else driver.status,
    }


def _validate_carrier(db: Session, tenant_id: int, carrier_id: int | None) -> None:
    if carrier_id is None:
        return
    exists = db.get(Carrier, carrier_id)
    if exists is None or exists.tenant_id != tenant_id:
        raise ValidationFailedError("Transportadora informada não existe ou não pertence à sua empresa.")


def list_drivers(
    db: Session, tenant_id: int, *, query: str | None, status: str | None, limit: int, offset: int,
) -> tuple[list[Driver], int]:
    return DriverRepository(db, tenant_id).search(query=query, status=status, limit=limit, offset=offset)


def get_driver(db: Session, tenant_id: int, driver_id: int) -> Driver:
    driver = DriverRepository(db, tenant_id).get(driver_id)
    if driver is None:
        raise NotFoundError("Motorista não encontrado.")
    return driver


def create_driver(
    db: Session, tenant_id: int, actor: User, payload: DriverCreate, ip_address: str | None,
) -> Driver:
    repo = DriverRepository(db, tenant_id)
    if repo.get_by_cpf(payload.cpf) is not None:
        raise ConflictError("Já existe um motorista cadastrado com este CPF.")
    _validate_carrier(db, tenant_id, payload.carrier_id)

    driver = Driver(
        tenant_id=tenant_id, full_name=payload.full_name, cpf=payload.cpf, cnh_number=payload.cnh_number,
        cnh_category=payload.cnh_category, cnh_expiry=payload.cnh_expiry, phone=payload.phone,
        carrier_id=payload.carrier_id, created_by=actor.id, updated_by=actor.id,
    )
    repo.add(driver)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.CREATE, table_name="drivers",
        record_id=str(driver.id), ip_address=ip_address, new_value=_as_dict(driver),
    )
    db.commit()
    db.refresh(driver)
    return driver


def update_driver(
    db: Session, tenant_id: int, actor: User, driver_id: int, payload: DriverUpdate, ip_address: str | None,
) -> Driver:
    repo = DriverRepository(db, tenant_id)
    driver = get_driver(db, tenant_id, driver_id)
    old_value = _as_dict(driver)

    if payload.cpf and payload.cpf != driver.cpf:
        existing = repo.get_by_cpf(payload.cpf)
        if existing is not None and existing.id != driver.id:
            raise ConflictError("Já existe um motorista cadastrado com este CPF.")
    if payload.carrier_id is not None:
        _validate_carrier(db, tenant_id, payload.carrier_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(driver, field, value)
    driver.updated_by = actor.id
    db.flush()

    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.UPDATE, table_name="drivers",
        record_id=str(driver.id), ip_address=ip_address, old_value=old_value, new_value=_as_dict(driver),
    )
    db.commit()
    db.refresh(driver)
    return driver


def delete_driver(db: Session, tenant_id: int, actor: User, driver_id: int, ip_address: str | None) -> None:
    repo = DriverRepository(db, tenant_id)
    driver = get_driver(db, tenant_id, driver_id)
    old_value = _as_dict(driver)
    repo.soft_delete(driver)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.DELETE, table_name="drivers",
        record_id=str(driver_id), ip_address=ip_address, old_value=old_value,
    )
    db.commit()
