"""`/api/v1/drivers` — motoristas (seção 10)."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.enums import DriverStatus
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.driver import DriverCreate, DriverOut, DriverUpdate
from app.services import driver_service

router = APIRouter(prefix="/drivers", tags=["drivers"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=Page[DriverOut])
def list_drivers(
    request: Request,
    params: PageParams = Depends(),
    q: str | None = Query(default=None, description="Busca por nome ou CPF"),
    status: DriverStatus | None = None,
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("drivers.view")),
    db: Session = Depends(get_db),
) -> Page[DriverOut]:
    items, total = driver_service.list_drivers(
        db, tenant_id, query=q, status=status, limit=params.page_size, offset=params.offset,
    )
    return Page.build([DriverOut.model_validate(item) for item in items], total=total, params=params)


@router.post("", response_model=DriverOut, status_code=201)
def create_driver(
    payload: DriverCreate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("drivers.manage")), db: Session = Depends(get_db),
) -> DriverOut:
    driver = driver_service.create_driver(db, tenant_id, user, payload, _client_ip(request))
    return DriverOut.model_validate(driver)


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(
    driver_id: int, tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("drivers.view")), db: Session = Depends(get_db),
) -> DriverOut:
    return DriverOut.model_validate(driver_service.get_driver(db, tenant_id, driver_id))


@router.patch("/{driver_id}", response_model=DriverOut)
def update_driver(
    driver_id: int, payload: DriverUpdate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("drivers.manage")), db: Session = Depends(get_db),
) -> DriverOut:
    driver = driver_service.update_driver(db, tenant_id, user, driver_id, payload, _client_ip(request))
    return DriverOut.model_validate(driver)


@router.delete("/{driver_id}", status_code=204)
def delete_driver(
    driver_id: int, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("drivers.manage")), db: Session = Depends(get_db),
) -> None:
    driver_service.delete_driver(db, tenant_id, user, driver_id, _client_ip(request))
