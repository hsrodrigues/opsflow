"""`/api/v1/occurrences` (seção 14)."""
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.enums import OccurrenceSeverity, OccurrenceStatus
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.occurrence import OccurrenceCreate, OccurrenceOut, OccurrenceUpdate
from app.services import occurrence_service
from app.services.occurrence_service import occurrence_to_out

router = APIRouter(prefix="/occurrences", tags=["occurrences"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=Page[OccurrenceOut])
def list_occurrences(
    request: Request,
    params: PageParams = Depends(),
    severity: OccurrenceSeverity | None = None,
    status: OccurrenceStatus | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("occurrences.view")),
    db: Session = Depends(get_db),
) -> Page[OccurrenceOut]:
    items, total = occurrence_service.list_occurrences(
        db, tenant_id, severity=severity, status=status, start_date=start_date, end_date=end_date,
        limit=params.page_size, offset=params.offset,
    )
    return Page.build([occurrence_to_out(item) for item in items], total=total, params=params)


@router.post("", response_model=OccurrenceOut, status_code=201)
def create_occurrence(
    payload: OccurrenceCreate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("occurrences.manage")), db: Session = Depends(get_db),
) -> OccurrenceOut:
    occurrence = occurrence_service.create_occurrence(db, tenant_id, user, payload, _client_ip(request))
    return occurrence_to_out(occurrence)


@router.get("/{occurrence_id}", response_model=OccurrenceOut)
def get_occurrence(
    occurrence_id: int, tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("occurrences.view")), db: Session = Depends(get_db),
) -> OccurrenceOut:
    return occurrence_to_out(occurrence_service.get_occurrence(db, tenant_id, occurrence_id))


@router.patch("/{occurrence_id}", response_model=OccurrenceOut)
def update_occurrence(
    occurrence_id: int, payload: OccurrenceUpdate, request: Request, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("occurrences.manage")), db: Session = Depends(get_db),
) -> OccurrenceOut:
    occurrence = occurrence_service.update_occurrence(db, tenant_id, user, occurrence_id, payload, _client_ip(request))
    return occurrence_to_out(occurrence)
