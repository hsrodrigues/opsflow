"""`/api/v1/carriers` — transportadoras (seção 11)."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.enums import CarrierStatus
from app.models.user import User
from app.schemas.carrier import CarrierCreate, CarrierOut, CarrierUpdate
from app.schemas.common import Page, PageParams
from app.services import carrier_service

router = APIRouter(prefix="/carriers", tags=["carriers"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=Page[CarrierOut])
def list_carriers(
    request: Request,
    params: PageParams = Depends(),
    q: str | None = Query(default=None, description="Busca por razão social, nome fantasia ou CNPJ"),
    status: CarrierStatus | None = None,
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("carriers.view")),
    db: Session = Depends(get_db),
) -> Page[CarrierOut]:
    items, total = carrier_service.list_carriers(
        db, tenant_id, query=q, status=status, limit=params.page_size, offset=params.offset,
    )
    return Page.build([CarrierOut.model_validate(item) for item in items], total=total, params=params)


@router.post("", response_model=CarrierOut, status_code=201)
def create_carrier(
    payload: CarrierCreate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("carriers.manage")), db: Session = Depends(get_db),
) -> CarrierOut:
    carrier = carrier_service.create_carrier(db, tenant_id, user, payload, _client_ip(request))
    return CarrierOut.model_validate(carrier)


@router.get("/{carrier_id}", response_model=CarrierOut)
def get_carrier(
    carrier_id: int, tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("carriers.view")), db: Session = Depends(get_db),
) -> CarrierOut:
    return CarrierOut.model_validate(carrier_service.get_carrier(db, tenant_id, carrier_id))


@router.patch("/{carrier_id}", response_model=CarrierOut)
def update_carrier(
    carrier_id: int, payload: CarrierUpdate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("carriers.manage")), db: Session = Depends(get_db),
) -> CarrierOut:
    carrier = carrier_service.update_carrier(db, tenant_id, user, carrier_id, payload, _client_ip(request))
    return CarrierOut.model_validate(carrier)


@router.delete("/{carrier_id}", status_code=204)
def delete_carrier(
    carrier_id: int, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("carriers.manage")), db: Session = Depends(get_db),
) -> None:
    carrier_service.delete_carrier(db, tenant_id, user, carrier_id, _client_ip(request))
