"""`/api/v1/schedules` — programação operacional (seção 13)."""
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.enums import ScheduleStatus
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.schedule import (
    DuplicateScheduleRequest,
    DuplicateScheduleResult,
    ScheduleItemCreate,
    ScheduleItemOut,
    ScheduleItemUpdate,
    StatusChangeRequest,
    StatusHistoryOut,
)
from app.services import schedule_service
from app.services.schedule_service import schedule_item_to_out

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/items", response_model=Page[ScheduleItemOut])
def list_schedule_items(
    request: Request,
    params: PageParams = Depends(),
    schedule_date: date | None = Query(default=None),
    status: ScheduleStatus | None = None,
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("schedules.view")),
    db: Session = Depends(get_db),
) -> Page[ScheduleItemOut]:
    items, total = schedule_service.list_schedule_items(
        db, tenant_id, schedule_date=schedule_date, status=status, limit=params.page_size, offset=params.offset,
    )
    return Page.build([schedule_item_to_out(item) for item in items], total=total, params=params)


@router.post("/items", response_model=ScheduleItemOut, status_code=201)
def create_schedule_item(
    payload: ScheduleItemCreate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("schedules.manage")), db: Session = Depends(get_db),
) -> ScheduleItemOut:
    item = schedule_service.create_schedule_item(db, tenant_id, user, payload, _client_ip(request))
    return schedule_item_to_out(item)


@router.get("/items/{item_id}", response_model=ScheduleItemOut)
def get_schedule_item(
    item_id: int, tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("schedules.view")), db: Session = Depends(get_db),
) -> ScheduleItemOut:
    return schedule_item_to_out(schedule_service.get_schedule_item(db, tenant_id, item_id))


@router.patch("/items/{item_id}", response_model=ScheduleItemOut)
def update_schedule_item(
    item_id: int, payload: ScheduleItemUpdate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("schedules.manage")), db: Session = Depends(get_db),
) -> ScheduleItemOut:
    item = schedule_service.update_schedule_item(db, tenant_id, user, item_id, payload, _client_ip(request))
    return schedule_item_to_out(item)


@router.delete("/items/{item_id}", status_code=204)
def delete_schedule_item(
    item_id: int, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("schedules.manage")), db: Session = Depends(get_db),
) -> None:
    schedule_service.delete_schedule_item(db, tenant_id, user, item_id, _client_ip(request))


@router.post("/items/{item_id}/status", response_model=ScheduleItemOut)
def change_schedule_item_status(
    item_id: int, payload: StatusChangeRequest, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("operations.update_status")), db: Session = Depends(get_db),
) -> ScheduleItemOut:
    item = schedule_service.change_status(
        db, tenant_id, user.id, item_id, payload.status, payload.notes, _client_ip(request),
    )
    return schedule_item_to_out(item)


@router.get("/items/{item_id}/history", response_model=list[StatusHistoryOut])
def get_schedule_item_history(
    item_id: int, tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("schedules.view")), db: Session = Depends(get_db),
) -> list[StatusHistoryOut]:
    return schedule_service.get_status_history(db, tenant_id, item_id)


@router.post("/duplicate", response_model=DuplicateScheduleResult)
def duplicate_schedule(
    payload: DuplicateScheduleRequest, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("schedules.manage")), db: Session = Depends(get_db),
) -> DuplicateScheduleResult:
    items_created = schedule_service.duplicate_schedule_day(
        db, tenant_id, user, payload.source_date, payload.target_date, _client_ip(request),
    )
    return DuplicateScheduleResult(items_created=items_created)
