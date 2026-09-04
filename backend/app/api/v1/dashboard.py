"""`/api/v1/dashboard` (seção 15/16)."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardCharts, DashboardSummary
from app.services import dashboard_service
from app.services.dashboard_service import DashboardFilters

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _filters_dependency(
    period_start: date | None = None, period_end: date | None = None, carrier_id: int | None = None,
    vehicle_id: int | None = None, route_id: int | None = None, status: str | None = None,
    shift: str | None = None,
) -> DashboardFilters:
    return DashboardFilters(
        period_start=period_start, period_end=period_end, carrier_id=carrier_id, vehicle_id=vehicle_id,
        route_id=route_id, status=status, shift=shift,
    )


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    filters: DashboardFilters = Depends(_filters_dependency),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    return dashboard_service.get_summary(db, tenant_id, filters)


@router.get("/charts", response_model=DashboardCharts)
def get_dashboard_charts(
    filters: DashboardFilters = Depends(_filters_dependency),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
) -> DashboardCharts:
    return dashboard_service.get_charts(db, tenant_id, filters)
