"""Activation service — a prospective customer redeeming a `license_key` a
`SUPER_ADMIN` generated for them (seção 6), with no account yet. Reuses
`auth_service.login` at the end so the newly-created admin lands logged in
immediately — no separate "now go log in" step after just typing a company
name, e-mail and password.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ValidationFailedError
from app.core.security import hash_password
from app.models.enums import AuditAction, LicenseStatus, UserStatus
from app.models.license import License
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.user_repository import get_user_by_email
from app.schemas.activation import ActivationRequest
from app.schemas.auth import TokenResponse
from app.services import auth_service
from app.services.audit_service import write_audit_log


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def activate_license_key(
    db: Session, payload: ActivationRequest, ip_address: str | None, user_agent: str | None,
) -> TokenResponse:
    license_ = db.execute(select(License).where(License.license_key == payload.license_key)).scalar_one_or_none()
    if license_ is None:
        raise ValidationFailedError("Chave de ativação inválida.")
    if license_.tenant_id is not None:
        raise ConflictError("Esta chave já foi ativada.")

    if payload.cnpj:
        existing = db.execute(select(Tenant).where(Tenant.cnpj == payload.cnpj)).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Já existe uma empresa cadastrada com este CNPJ.")
    if get_user_by_email(db, payload.admin_email) is not None:
        raise ConflictError("Já existe uma conta com este e-mail.")

    tenant = Tenant(legal_name=payload.legal_name, trade_name=payload.trade_name, cnpj=payload.cnpj)
    db.add(tenant)
    db.flush()

    now = _utc_now()
    license_.tenant_id = tenant.id
    license_.status = LicenseStatus.TRIAL
    license_.issued_at = now
    license_.expires_at = now + timedelta(days=license_.pending_trial_days or 30)
    license_.activated_at = now

    admin_role = db.query(Role).filter(Role.code == "ADMIN_EMPRESA").one()
    admin_user = User(
        tenant_id=tenant.id, email=payload.admin_email.strip().lower(), full_name=payload.admin_full_name,
        password_hash=hash_password(payload.admin_password), status=UserStatus.ATIVO,
    )
    admin_user.roles = [admin_role]
    db.add(admin_user)
    db.flush()

    write_audit_log(
        db, tenant_id=tenant.id, user_id=admin_user.id, action=AuditAction.CREATE, table_name="tenants",
        record_id=str(tenant.id), ip_address=ip_address, new_value={"activated_via_key": True},
    )
    db.commit()

    return auth_service.login(
        db, email=payload.admin_email, password=payload.admin_password, remember=True,
        ip_address=ip_address, user_agent=user_agent,
    )
