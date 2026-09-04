"""`/api/v1/routes` — rotas (seção 12)."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.enums import RouteStatus
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.route import RouteCreate, RouteOut, RouteUpdate
from app.services import route_service
from app.services.route_service import route_to_out

router = APIRouter(prefix="/routes", tags=["routes"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=Page[RouteOut])
def list_routes(
    request: Request,
    params: PageParams = Depends(),
    q: str | None = Query(default=None, description="Busca por nome da rota"),
    status: RouteStatus | None = None,
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("routes.view")),
    db: Session = Depends(get_db),
) -> Page[RouteOut]:
    items, total = route_service.list_routes(
        db, tenant_id, query=q, status=status, limit=params.page_size, offset=params.offset,
    )
    return Page.build([route_to_out(item) for item in items], total=total, params=params)


@router.post("", response_model=RouteOut, status_code=201)
def create_route(
    payload: RouteCreate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("routes.manage")), db: Session = Depends(get_db),
) -> RouteOut:
    route = route_service.create_route(db, tenant_id, user, payload, _client_ip(request))
    return route_to_out(route)


@router.get("/{route_id}", response_model=RouteOut)
def get_route(
    route_id: int, tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("routes.view")), db: Session = Depends(get_db),
) -> RouteOut:
    return route_to_out(route_service.get_route(db, tenant_id, route_id))


@router.patch("/{route_id}", response_model=RouteOut)
def update_route(
    route_id: int, payload: RouteUpdate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("routes.manage")), db: Session = Depends(get_db),
) -> RouteOut:
    route = route_service.update_route(db, tenant_id, user, route_id, payload, _client_ip(request))
    return route_to_out(route)


@router.delete("/{route_id}", status_code=204)
def delete_route(
    route_id: int, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("routes.manage")), db: Session = Depends(get_db),
) -> None:
    route_service.delete_route(db, tenant_id, user, route_id, _client_ip(request))
