"""`/api/v1/vehicles` — veículos (seção 9)."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.enums import VehicleStatus
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.vehicle import VehicleCreate, VehicleOut, VehicleUpdate
from app.services import vehicle_service

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=Page[VehicleOut])
def list_vehicles(
    request: Request,
    params: PageParams = Depends(),
    q: str | None = Query(default=None, description="Busca por placa, marca ou modelo"),
    status: VehicleStatus | None = None,
    carrier_id: int | None = None,
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("vehicles.view")),
    db: Session = Depends(get_db),
) -> Page[VehicleOut]:
    items, total = vehicle_service.list_vehicles(
        db, tenant_id, query=q, status=status, carrier_id=carrier_id,
        limit=params.page_size, offset=params.offset,
    )
    return Page.build([VehicleOut.model_validate(item) for item in items], total=total, params=params)


@router.post("", response_model=VehicleOut, status_code=201)
def create_vehicle(
    payload: VehicleCreate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("vehicles.manage")), db: Session = Depends(get_db),
) -> VehicleOut:
    vehicle = vehicle_service.create_vehicle(db, tenant_id, user, payload, _client_ip(request))
    return VehicleOut.model_validate(vehicle)


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(
    vehicle_id: int, tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("vehicles.view")), db: Session = Depends(get_db),
) -> VehicleOut:
    return VehicleOut.model_validate(vehicle_service.get_vehicle(db, tenant_id, vehicle_id))


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(
    vehicle_id: int, payload: VehicleUpdate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("vehicles.manage")), db: Session = Depends(get_db),
) -> VehicleOut:
    vehicle = vehicle_service.update_vehicle(db, tenant_id, user, vehicle_id, payload, _client_ip(request))
    return VehicleOut.model_validate(vehicle)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: int, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("vehicles.manage")), db: Session = Depends(get_db),
) -> None:
    vehicle_service.delete_vehicle(db, tenant_id, user, vehicle_id, _client_ip(request))
