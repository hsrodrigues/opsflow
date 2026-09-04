"""Authentication service — orchestrates the login/refresh/logout flows (seção 5).

This is the one place that decides *how* login works (lockout, license
status, token issuance); `app/api/v1/auth.py` only translates HTTP
in/out, and the repositories only know how to fetch/persist rows.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, generate_refresh_token, verify_password
from app.models.enums import AuditAction, UserStatus
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import get_user_by_email
from app.schemas.auth import TokenResponse, UserInfo
from app.services.audit_service import write_audit_log
from app.services.license_service import build_license_info, get_latest_license


def _utc_now() -> datetime:
    """Current UTC time, naive (matches the naive `DateTime` columns in the schema)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_user_info(user: User) -> UserInfo:
    role_codes = sorted({role.code.value if hasattr(role.code, "value") else role.code for role in user.roles})
    permission_codes = sorted(
        {permission.code for role in user.roles for permission in role.permissions}
    )
    return UserInfo(
        id=user.id, email=user.email, full_name=user.full_name, tenant_id=user.tenant_id,
        roles=role_codes, permissions=permission_codes,
    )


def login(
    db: Session, *, email: str, password: str, remember: bool, ip_address: str | None, user_agent: str | None,
) -> TokenResponse:
    """Authenticate a user and issue a new access/refresh token pair."""
    settings = get_settings()
    user = get_user_by_email(db, email)

    generic_error = UnauthorizedError("E-mail ou senha inválidos.")
    if user is None:
        raise generic_error

    if user.status != UserStatus.ATIVO:
        raise UnauthorizedError("Esta conta está inativa ou bloqueada. Contate o administrador.")

    if user.locked_until is not None and user.locked_until > _utc_now():
        raise UnauthorizedError(
            "Conta temporariamente bloqueada por excesso de tentativas. Tente novamente mais tarde."
        )

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.max_login_attempts:
            user.locked_until = _utc_now() + timedelta(minutes=settings.login_lockout_minutes)
        db.flush()
        db.commit()
        raise generic_error

    tenant = user.tenant
    if tenant is not None and not tenant.is_active:
        raise ForbiddenError("Esta empresa está inativa. Contate o suporte.")

    license_ = get_latest_license(db, user.tenant_id) if user.tenant_id is not None else None

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = _utc_now()
    user.remember_login = remember

    access_token, expires_at = create_access_token(user_id=user.id, tenant_id=user.tenant_id)
    raw_refresh_token = generate_refresh_token()
    RefreshTokenRepository(db).create(
        user_id=user.id, raw_token=raw_refresh_token, issued_at=_utc_now(),
        expires_at=_utc_now() + timedelta(days=settings.refresh_token_expire_days),
        ip_address=ip_address, user_agent=user_agent,
    )
    write_audit_log(
        db, tenant_id=user.tenant_id, user_id=user.id, action=AuditAction.LOGIN,
        table_name="users", record_id=str(user.id), ip_address=ip_address,
    )

    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=access_token, refresh_token=raw_refresh_token, expires_at=expires_at,
        user=build_user_info(user), license=build_license_info(license_),
    )


def refresh(db: Session, *, raw_refresh_token: str, ip_address: str | None, user_agent: str | None) -> TokenResponse:
    """Rotate a refresh token: revoke the old one, issue a brand new pair."""
    settings = get_settings()
    repo = RefreshTokenRepository(db)
    token = repo.get_active_by_raw_token(raw_refresh_token)
    if token is None:
        raise UnauthorizedError("Sessão expirada. Faça login novamente.")

    user = db.get(User, token.user_id)
    if user is None or user.status != UserStatus.ATIVO:
        raise UnauthorizedError("Sessão expirada. Faça login novamente.")

    repo.revoke(token)

    license_ = get_latest_license(db, user.tenant_id) if user.tenant_id is not None else None
    access_token, expires_at = create_access_token(user_id=user.id, tenant_id=user.tenant_id)
    new_raw_refresh_token = generate_refresh_token()
    repo.create(
        user_id=user.id, raw_token=new_raw_refresh_token, issued_at=_utc_now(),
        expires_at=_utc_now() + timedelta(days=settings.refresh_token_expire_days),
        ip_address=ip_address, user_agent=user_agent,
    )
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=access_token, refresh_token=new_raw_refresh_token, expires_at=expires_at,
        user=build_user_info(user), license=build_license_info(license_),
    )


def logout(db: Session, *, raw_refresh_token: str, ip_address: str | None) -> None:
    """Revoke a single refresh-token session (seção 5: "controle de sessões")."""
    repo = RefreshTokenRepository(db)
    token = repo.get_active_by_raw_token(raw_refresh_token)
    if token is None:
        return  # já inválido/expirado — logout é idempotente, não é erro
    repo.revoke(token)
    write_audit_log(
        db, tenant_id=None, user_id=token.user_id, action=AuditAction.LOGOUT,
        table_name="users", record_id=str(token.user_id), ip_address=ip_address,
    )
    db.commit()
