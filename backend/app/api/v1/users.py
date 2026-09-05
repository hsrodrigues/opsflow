"""`/api/v1/users` — gestão de equipe dentro da empresa (seção 4/5).

Não há `DELETE`: uma conta nunca é apagada de fato (perderia o autor do
histórico de auditoria/operações passadas) — "remover" um usuário é
desativá-lo via `PATCH { "status": "INATIVO" }`, e ele para de conseguir
logar (ver `auth_service.login`).
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.enums import UserStatus
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.user import UserCreate, UserOut, UserPasswordReset, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=Page[UserOut])
def list_users(
    request: Request,
    params: PageParams = Depends(),
    q: str | None = Query(default=None, description="Busca por nome ou e-mail"),
    status: UserStatus | None = None,
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("users.view")),
    db: Session = Depends(get_db),
) -> Page[UserOut]:
    items, total = user_service.list_users(
        db, tenant_id, query=q, status=status, limit=params.page_size, offset=params.offset,
    )
    return Page.build([user_service.user_to_out(item) for item in items], total=total, params=params)


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("users.manage")), db: Session = Depends(get_db),
) -> UserOut:
    created = user_service.create_user(db, tenant_id, user, payload, _client_ip(request))
    return user_service.user_to_out(created)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int, tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("users.view")), db: Session = Depends(get_db),
) -> UserOut:
    return user_service.user_to_out(user_service.get_user(db, tenant_id, user_id))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, payload: UserUpdate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("users.manage")), db: Session = Depends(get_db),
) -> UserOut:
    updated = user_service.update_user(db, tenant_id, user, user_id, payload, _client_ip(request))
    return user_service.user_to_out(updated)


@router.post("/{user_id}/reset-password", status_code=204)
def reset_password(
    user_id: int, payload: UserPasswordReset, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("users.manage")), db: Session = Depends(get_db),
) -> None:
    user_service.reset_password(db, tenant_id, user, user_id, payload, _client_ip(request))
