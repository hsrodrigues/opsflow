"""License lookup and plan-limit enforcement (seção 6/7).

Centralizes the "effective limit" rule — a `License` only overrides its
`Plan`'s `max_users`/`max_vehicles` when it sets its own value; otherwise it
simply inherits the plan's — so both the login response (`auth_service`)
and every creation endpoint that must reject "limite do plano atingido"
(seção 6) agree on exactly the same numbers.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import LicenseError, NotFoundError
from app.models.license import License
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.auth import LicenseInfo
from app.schemas.license import LicenseSummary


def get_latest_license(db: Session, tenant_id: int) -> License | None:
    stmt = select(License).where(License.tenant_id == tenant_id).order_by(License.issued_at.desc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def get_effective_limits(license_: License | None) -> tuple[int | None, int | None]:
    """Return (max_users, max_vehicles) actually in effect. `None` means unlimited."""
    if license_ is None:
        return None, None
    plan = license_.plan
    max_users = license_.max_users if license_.max_users is not None else (plan.max_users if plan else None)
    max_vehicles = (
        license_.max_vehicles if license_.max_vehicles is not None else (plan.max_vehicles if plan else None)
    )
    return max_users, max_vehicles


def build_license_info(license_: License | None) -> LicenseInfo | None:
    """Build the API's license summary — always the *effective* limits, never the raw column."""
    if license_ is None:
        return None
    status = license_.status.value if hasattr(license_.status, "value") else license_.status
    plan = license_.plan
    max_users, max_vehicles = get_effective_limits(license_)
    return LicenseInfo(
        status=status, plan_code=plan.code.value if plan else "",
        expires_at=license_.expires_at, max_users=max_users, max_vehicles=max_vehicles,
    )


def _count_active(db: Session, model, tenant_id: int) -> int:
    stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    if hasattr(model, "deleted_at"):
        stmt = stmt.where(model.deleted_at.is_(None))
    return db.execute(stmt).scalar_one()


def enforce_vehicle_limit(db: Session, tenant_id: int) -> None:
    """Raise `LicenseError` (`OF-API-402`) if the tenant is already at its vehicle limit."""
    _, max_vehicles = get_effective_limits(get_latest_license(db, tenant_id))
    if max_vehicles is None:
        return
    if _count_active(db, Vehicle, tenant_id) >= max_vehicles:
        raise LicenseError(
            f"Limite de {max_vehicles} veículos do seu plano atingido. Faça upgrade para cadastrar mais."
        )


def enforce_user_limit(db: Session, tenant_id: int) -> None:
    """Raise `LicenseError` (`OF-API-402`) if the tenant is already at its user limit."""
    max_users, _ = get_effective_limits(get_latest_license(db, tenant_id))
    if max_users is None:
        return
    if _count_active(db, User, tenant_id) >= max_users:
        raise LicenseError(f"Limite de {max_users} usuários do seu plano atingido. Faça upgrade para adicionar mais.")


def build_license_summary(db: Session, tenant_id: int) -> LicenseSummary:
    license_ = get_latest_license(db, tenant_id)
    if license_ is None:
        raise NotFoundError("Nenhuma licença encontrada para esta empresa.")
    plan = license_.plan
    max_users, max_vehicles = get_effective_limits(license_)
    status = license_.status.value if hasattr(license_.status, "value") else license_.status
    return LicenseSummary(
        plan_code=plan.code.value if plan and hasattr(plan.code, "value") else (plan.code if plan else ""),
        plan_name=plan.name if plan else "—", status=status,
        issued_at=license_.issued_at, expires_at=license_.expires_at,
        max_users=max_users, max_vehicles=max_vehicles,
        current_users=_count_active(db, User, tenant_id), current_vehicles=_count_active(db, Vehicle, tenant_id),
    )
