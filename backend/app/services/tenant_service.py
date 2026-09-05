"""Tenant service — gestão de empresas clientes por um `SUPER_ADMIN`
(seção 54).

Deliberadamente sem `TenantRepository`: cada função aqui opera *através* de
tenants, não dentro de um — exatamente a exceção que o docstring de
`app/repositories/base.py` reserva para "um repositório de plataforma
explícito (sem filtro de tenant)". Ver `app/api/deps.
require_platform_admin` para o enforcement de que só `SUPER_ADMIN` chega
até aqui.
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.security import hash_password
from app.models.enums import AuditAction, LicenseStatus, UserStatus
from app.models.license import License
from app.models.plan import Plan
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.models.vehicle import Vehicle
from app.repositories.user_repository import get_user_by_email
from app.schemas.platform import (
    LicenseKeyCreate,
    LicenseKeyOut,
    TenantCreate,
    TenantLicenseUpdate,
    TenantOut,
    TenantUpdate,
)
from app.services.audit_service import write_audit_log
from app.services.license_service import get_effective_limits, get_latest_license


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _tenant_to_out(db: Session, tenant: Tenant) -> TenantOut:
    license_ = get_latest_license(db, tenant.id)
    max_users, max_vehicles = get_effective_limits(license_)
    user_count = db.execute(
        select(func.count()).select_from(User).where(User.tenant_id == tenant.id)
    ).scalar_one()
    vehicle_count = db.execute(
        select(func.count()).select_from(Vehicle)
        .where(Vehicle.tenant_id == tenant.id, Vehicle.deleted_at.is_(None))
    ).scalar_one()
    return TenantOut(
        id=tenant.id, legal_name=tenant.legal_name, trade_name=tenant.trade_name, cnpj=tenant.cnpj,
        is_active=tenant.is_active, created_at=tenant.created_at,
        license_key=license_.license_key if license_ else None,
        plan_code=license_.plan.code.value if license_ and license_.plan else None,
        license_status=(license_.status.value if hasattr(license_.status, "value") else license_.status) if license_ else None,
        license_expires_at=license_.expires_at if license_ else None,
        max_users=max_users, max_vehicles=max_vehicles,
        max_users_override=license_.max_users if license_ else None,
        max_vehicles_override=license_.max_vehicles if license_ else None,
        user_count=user_count, vehicle_count=vehicle_count,
    )


def list_tenants(db: Session) -> list[TenantOut]:
    tenants = db.execute(select(Tenant).order_by(Tenant.legal_name)).scalars().all()
    return [_tenant_to_out(db, tenant) for tenant in tenants]


def get_tenant(db: Session, tenant_id: int) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Empresa não encontrada.")
    return tenant


def create_tenant(db: Session, actor: User, payload: TenantCreate, ip_address: str | None) -> TenantOut:
    if payload.cnpj:
        existing = db.execute(select(Tenant).where(Tenant.cnpj == payload.cnpj)).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Já existe uma empresa cadastrada com este CNPJ.")
    if get_user_by_email(db, payload.admin_email) is not None:
        raise ConflictError("Já existe uma conta com este e-mail.")

    plan = db.query(Plan).filter(Plan.code == payload.plan_code).one_or_none()
    if plan is None:
        raise ValidationFailedError(f"Plano inválido: {payload.plan_code!r}.")

    tenant = Tenant(legal_name=payload.legal_name, trade_name=payload.trade_name, cnpj=payload.cnpj)
    db.add(tenant)
    db.flush()

    now = _utc_now()
    license_ = License(
        tenant_id=tenant.id, plan_id=plan.id, license_key=secrets.token_hex(16),
        status=LicenseStatus.TRIAL, issued_at=now, expires_at=now + timedelta(days=payload.trial_days),
    )
    db.add(license_)

    admin_role = db.query(Role).filter(Role.code == "ADMIN_EMPRESA").one()
    admin_user = User(
        tenant_id=tenant.id, email=payload.admin_email.strip().lower(), full_name=payload.admin_full_name,
        password_hash=hash_password(payload.admin_password), status=UserStatus.ATIVO,
    )
    admin_user.roles = [admin_role]
    db.add(admin_user)
    db.flush()

    write_audit_log(
        db, tenant_id=None, user_id=actor.id, action=AuditAction.CREATE, table_name="tenants",
        record_id=str(tenant.id), ip_address=ip_address, new_value={"legal_name": tenant.legal_name},
    )
    db.commit()
    db.refresh(tenant)
    return _tenant_to_out(db, tenant)


def update_tenant(
    db: Session, actor: User, tenant_id: int, payload: TenantUpdate, ip_address: str | None,
) -> TenantOut:
    tenant = get_tenant(db, tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    db.flush()
    write_audit_log(
        db, tenant_id=None, user_id=actor.id, action=AuditAction.UPDATE, table_name="tenants",
        record_id=str(tenant.id), ip_address=ip_address,
    )
    db.commit()
    db.refresh(tenant)
    return _tenant_to_out(db, tenant)


def regenerate_license_key(db: Session, actor: User, tenant_id: int, ip_address: str | None) -> TenantOut:
    """Emite uma nova `license_key` para a empresa — o "código de ativação"
    do produto (seção 6): um identificador público que o cliente pode
    exibir/repassar, nunca o segredo em si (a validação de status/expiração/
    limites é sempre feita server-side, nunca a partir do valor da chave).
    """
    tenant = get_tenant(db, tenant_id)
    license_ = get_latest_license(db, tenant_id)
    if license_ is None:
        raise NotFoundError("Esta empresa ainda não tem nenhuma licença.")

    license_.license_key = secrets.token_hex(16)
    db.flush()

    write_audit_log(
        db, tenant_id=None, user_id=actor.id, action=AuditAction.UPDATE, table_name="licenses",
        record_id=str(license_.id), ip_address=ip_address, new_value={"license_key_regenerated": True},
    )
    db.commit()
    db.refresh(tenant)
    return _tenant_to_out(db, tenant)


def update_tenant_license(
    db: Session, actor: User, tenant_id: int, payload: TenantLicenseUpdate, ip_address: str | None,
) -> TenantOut:
    """`exclude_unset=True` (não um `is not None` campo a campo, como este
    código já teve): um PATCH precisa distinguir "não mandei esse campo,
    deixa como está" de "mandei esse campo como null, de propósito, LIMPA
    esse valor" — só assim dá pra, por exemplo, tornar uma licença
    permanente (`expires_at: null`) ou voltar `max_users`/`max_vehicles` a
    usar o limite do plano de novo. Um `is not None` trata as duas coisas
    como idênticas e nunca deixa limpar nada — bug real reportado pelo
    usuário ("mesmo mudando pra ativada a data de expiração não sai").
    """
    tenant = get_tenant(db, tenant_id)
    license_ = get_latest_license(db, tenant_id)
    if license_ is None:
        raise NotFoundError("Esta empresa ainda não tem nenhuma licença.")

    fields = payload.model_dump(exclude_unset=True)
    if "plan_code" in fields:
        plan_code = fields.pop("plan_code")
        plan = db.query(Plan).filter(Plan.code == plan_code).one_or_none()
        if plan is None:
            raise ValidationFailedError(f"Plano inválido: {plan_code!r}.")
        license_.plan_id = plan.id
    for field, value in fields.items():
        setattr(license_, field, value)
    db.flush()

    write_audit_log(
        db, tenant_id=None, user_id=actor.id, action=AuditAction.UPDATE, table_name="licenses",
        record_id=str(license_.id), ip_address=ip_address,
    )
    db.commit()
    db.refresh(tenant)
    return _tenant_to_out(db, tenant)


def _license_key_to_out(license_: License) -> LicenseKeyOut:
    return LicenseKeyOut(
        id=license_.id, license_key=license_.license_key,
        plan_code=license_.plan.code.value if hasattr(license_.plan.code, "value") else license_.plan.code,
        pending_trial_days=license_.pending_trial_days, issued_at=license_.issued_at,
        activated_at=license_.activated_at, tenant_id=license_.tenant_id,
        tenant_name=license_.tenant.legal_name if license_.tenant else None,
    )


def generate_license_key(db: Session, actor: User, payload: LicenseKeyCreate, ip_address: str | None) -> LicenseKeyOut:
    """Gera uma chave "solta" (seção 6): sem empresa vinculada ainda. O
    cliente a resgata sozinho em `POST /api/v1/activation/activate`, que
    preenche `tenant_id` nesta MESMA linha — nunca cria uma segunda
    licença.
    """
    plan = db.query(Plan).filter(Plan.code == payload.plan_code).one_or_none()
    if plan is None:
        raise ValidationFailedError(f"Plano inválido: {payload.plan_code!r}.")

    license_ = License(
        tenant_id=None, plan_id=plan.id, license_key=secrets.token_hex(16),
        status=LicenseStatus.TRIAL, issued_at=_utc_now(), expires_at=None,
        pending_trial_days=payload.trial_days,
    )
    db.add(license_)
    db.flush()

    write_audit_log(
        db, tenant_id=None, user_id=actor.id, action=AuditAction.CREATE, table_name="licenses",
        record_id=str(license_.id), ip_address=ip_address, new_value={"license_key_generated": True},
    )
    db.commit()
    db.refresh(license_)
    return _license_key_to_out(license_)


def list_license_keys(db: Session) -> list[LicenseKeyOut]:
    licenses = db.execute(select(License).order_by(License.issued_at.desc())).scalars().all()
    return [_license_key_to_out(license_) for license_ in licenses]
