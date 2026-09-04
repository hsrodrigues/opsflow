"""`/api/v1/operations` — Centro de Operações (seção 21)."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.user import User
from app.schemas.operation import OperationOut, OperationsSummary
from app.services import operation_service

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=list[OperationOut])
def list_operations(
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("operations.view")),
    db: Session = Depends(get_db),
) -> list[OperationOut]:
    operations = operation_service.list_active_operations(db, tenant_id)
    return [operation_service.operation_to_out(op) for op in operations]


@router.get("/summary", response_model=OperationsSummary)
def get_operations_summary(
    summary_date: date | None = Query(default=None, alias="date"),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("operations.view")),
    db: Session = Depends(get_db),
) -> OperationsSummary:
    target_date = summary_date or datetime.now(timezone.utc).date()
    return operation_service.get_summary(db, tenant_id, target_date)
