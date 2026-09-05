"""Shared FastAPI dependencies: current user, permission enforcement.

`get_current_user` re-reads the user (and roles/permissions) from the
database on every request instead of trusting claims embedded in the JWT —
see the docstring on `create_access_token` for why. `require_permission`
builds on it to gate an endpoint on a specific RBAC permission code (seção
4), returning the friendly `ForbiddenError` (`OF-API-403`) rather than a
bare 403 when the check fails.
"""
from collections.abc import Callable

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.enums import UserStatus
from app.models.role import Role
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the `Authorization: Bearer <token>` header."""
    if credentials is None:
        raise UnauthorizedError("Não autenticado. Faça login novamente.")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Sessão expirada. Faça login novamente.") from None
    except jwt.PyJWTError:
        raise UnauthorizedError("Token inválido. Faça login novamente.") from None

    user_id = int(payload["sub"])
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user = db.execute(stmt).scalar_one_or_none()

    if user is None or user.status != UserStatus.ATIVO:
        raise UnauthorizedError("Sessão expirada. Faça login novamente.")

    request.state.current_user = user
    return user


def require_permission(permission_code: str) -> Callable[[User], User]:
    """Build a dependency that enforces `permission_code` on the current user's roles."""

    def _check(user: User = Depends(get_current_user)) -> User:
        user_permission_codes = {permission.code for role in user.roles for permission in role.permissions}
        if permission_code not in user_permission_codes:
            raise ForbiddenError(f"Você não tem permissão para executar esta ação ({permission_code}).")
        return user

    return _check


def get_current_tenant_id(user: User = Depends(get_current_user)) -> int:
    """Resolve the current request's tenant, for endpoints scoped to a single company.

    Raises when the caller is a `SUPER_ADMIN` (`tenant_id is None`) — platform
    admins managing a specific tenant's cadastros is out of scope for now
    (it would require an explicit "impersonate tenant" mechanism, not just
    reading a claim), so that case is rejected rather than silently guessing.
    """
    if user.tenant_id is None:
        raise ForbiddenError("Esta ação requer um usuário vinculado a uma empresa.")
    return user.tenant_id


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    """The mirror image of `get_current_tenant_id`: gate an endpoint to
    `SUPER_ADMIN` only (seção 54) — a platform operator managing tenants/
    licenses across companies, never a regular tenant user no matter their
    permissions. `SUPER_ADMIN` is the only role with `tenant_id is None`
    (`app/models/user.py`), which is what's actually checked — the role
    check on top is belt-and-suspenders documentation of intent, since
    nothing else can create a `tenant_id IS NULL` user through the API today.
    """
    if user.tenant_id is not None:
        raise ForbiddenError("Esta ação é exclusiva de administradores de plataforma.")
    role_codes = {role.code.value if hasattr(role.code, "value") else role.code for role in user.roles}
    if "SUPER_ADMIN" not in role_codes:
        raise ForbiddenError("Esta ação é exclusiva de administradores de plataforma.")
    return user
