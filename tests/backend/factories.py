"""Small test data builders shared across the backend test suite.

Not a full factory framework — just enough to build a tenant + user
consistently without repeating the same six lines in every test module.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.license import License
from app.models.location import Location
from app.models.plan import Plan
from app.models.role import Role
from app.models.route import Route
from app.models.tenant import Tenant
from app.models.user import User
from app.models.enums import LicenseStatus, UserStatus


def make_tenant(db: Session, *, legal_name: str = "Empresa Teste Ltda", cnpj: str | None = None) -> Tenant:
    tenant = Tenant(legal_name=legal_name, cnpj=cnpj)
    db.add(tenant)
    db.flush()
    return tenant


def make_license(db: Session, tenant: Tenant, *, status: LicenseStatus = LicenseStatus.ACTIVE) -> License:
    plan = db.query(Plan).filter(Plan.code == "PROFESSIONAL").one()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    license_ = License(
        tenant_id=tenant.id, plan_id=plan.id, license_key=f"test-key-{tenant.id}-{status}",
        status=status, issued_at=now, expires_at=now + timedelta(days=30),
    )
    db.add(license_)
    db.flush()
    return license_


def make_user(
    db: Session, tenant: Tenant | None, *, email: str, password: str = "Sup3rSecret!",
    role_code: str = "ADMIN_EMPRESA", status: UserStatus = UserStatus.ATIVO,
) -> User:
    role = db.query(Role).filter(Role.code == role_code).one()
    user = User(
        # Normalizado para minúsculas na criação, do mesmo jeito que o login
        # normaliza na busca (`get_user_by_email`) — a fonte da verdade é
        # sempre lowercase, nunca depende de quem está comparando lembrar disso.
        tenant_id=tenant.id if tenant else None, email=email.strip().lower(),
        password_hash=hash_password(password), full_name="Usuário de Teste", status=status,
    )
    user.roles.append(role)
    db.add(user)
    db.flush()
    return user


def make_route(db: Session, tenant: Tenant, *, name: str = "Rota Teste") -> Route:
    origin = Location(tenant_id=tenant.id, name=f"{name} - Origem")
    destination = Location(tenant_id=tenant.id, name=f"{name} - Destino")
    db.add_all([origin, destination])
    db.flush()
    route = Route(tenant_id=tenant.id, name=name, origin_location_id=origin.id, destination_location_id=destination.id)
    db.add(route)
    db.flush()
    return route
