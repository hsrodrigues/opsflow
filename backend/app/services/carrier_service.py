"""Carrier service — business rules for transportadoras (seção 11)."""
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.carrier import Carrier
from app.models.enums import AuditAction
from app.models.user import User
from app.repositories.carrier_repository import CarrierRepository
from app.schemas.carrier import CarrierCreate, CarrierUpdate
from app.services.audit_service import write_audit_log


def _as_dict(carrier: Carrier) -> dict:
    return {
        "legal_name": carrier.legal_name, "trade_name": carrier.trade_name, "cnpj": carrier.cnpj,
        "status": carrier.status.value if hasattr(carrier.status, "value") else carrier.status,
    }


def list_carriers(
    db: Session, tenant_id: int, *, query: str | None, status: str | None, limit: int, offset: int,
) -> tuple[list[Carrier], int]:
    return CarrierRepository(db, tenant_id).search(query=query, status=status, limit=limit, offset=offset)


def get_carrier(db: Session, tenant_id: int, carrier_id: int) -> Carrier:
    carrier = CarrierRepository(db, tenant_id).get(carrier_id)
    if carrier is None:
        raise NotFoundError("Transportadora não encontrada.")
    return carrier


def create_carrier(
    db: Session, tenant_id: int, actor: User, payload: CarrierCreate, ip_address: str | None,
) -> Carrier:
    repo = CarrierRepository(db, tenant_id)
    if payload.cnpj and repo.get_by_cnpj(payload.cnpj) is not None:
        raise ConflictError("Já existe uma transportadora cadastrada com este CNPJ.")

    carrier = Carrier(
        tenant_id=tenant_id, legal_name=payload.legal_name, trade_name=payload.trade_name, cnpj=payload.cnpj,
        contact_name=payload.contact_name, phone=payload.phone, email=payload.email, notes=payload.notes,
        created_by=actor.id, updated_by=actor.id,
    )
    repo.add(carrier)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.CREATE, table_name="carriers",
        record_id=str(carrier.id), ip_address=ip_address, new_value=_as_dict(carrier),
    )
    db.commit()
    db.refresh(carrier)
    return carrier


def update_carrier(
    db: Session, tenant_id: int, actor: User, carrier_id: int, payload: CarrierUpdate, ip_address: str | None,
) -> Carrier:
    repo = CarrierRepository(db, tenant_id)
    carrier = get_carrier(db, tenant_id, carrier_id)
    old_value = _as_dict(carrier)

    if payload.cnpj and payload.cnpj != carrier.cnpj:
        existing = repo.get_by_cnpj(payload.cnpj)
        if existing is not None and existing.id != carrier.id:
            raise ConflictError("Já existe uma transportadora cadastrada com este CNPJ.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(carrier, field, value)
    carrier.updated_by = actor.id
    db.flush()

    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.UPDATE, table_name="carriers",
        record_id=str(carrier.id), ip_address=ip_address, old_value=old_value, new_value=_as_dict(carrier),
    )
    db.commit()
    db.refresh(carrier)
    return carrier


def delete_carrier(db: Session, tenant_id: int, actor: User, carrier_id: int, ip_address: str | None) -> None:
    repo = CarrierRepository(db, tenant_id)
    carrier = get_carrier(db, tenant_id, carrier_id)
    old_value = _as_dict(carrier)
    repo.soft_delete(carrier)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.DELETE, table_name="carriers",
        record_id=str(carrier_id), ip_address=ip_address, old_value=old_value,
    )
    db.commit()
