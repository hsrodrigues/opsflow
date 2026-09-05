"""`/api/v1/reports` (seção 17): relatórios de Operações, Ocorrências,
Veículos e Transportadoras, com pré-visualização em JSON (`/preview`) e
exportação em CSV/Excel/PDF (`/export`) — os mesmos filtros de
período/turno/status/veículo/rota/transportadora do dashboard.
"""
import io
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.core.exceptions import ValidationFailedError
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.report import ReportPreview
from app.services import export_service, report_service
from app.services.dashboard_service import DashboardFilters
from app.services.report_service import ReportRequest

router = APIRouter(prefix="/reports", tags=["reports"])

_CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
_EXPORTERS = {"csv": export_service.to_csv, "xlsx": export_service.to_excel, "pdf": export_service.to_pdf}


def _filters_dependency(
    period_start: date | None = None, period_end: date | None = None, carrier_id: int | None = None,
    vehicle_id: int | None = None, route_id: int | None = None, status: str | None = None,
    shift: str | None = None,
) -> DashboardFilters:
    return DashboardFilters(
        period_start=period_start, period_end=period_end, carrier_id=carrier_id, vehicle_id=vehicle_id,
        route_id=route_id, status=status, shift=shift,
    )


def _tenant_name(db: Session, tenant_id: int) -> str:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        return "—"
    return tenant.trade_name or tenant.legal_name


@router.get("/preview", response_model=ReportPreview)
def preview_report(
    report_type: str, filters: DashboardFilters = Depends(_filters_dependency),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("reports.view")),
    db: Session = Depends(get_db),
) -> ReportPreview:
    if report_type not in report_service.REPORT_TYPES:
        raise ValidationFailedError(f"Tipo de relatório inválido: {report_type!r}.")
    document = report_service.build_report(
        db, tenant_id, _tenant_name(db, tenant_id), ReportRequest(report_type, filters),
    )
    return ReportPreview(
        title=document.title, subtitle=document.subtitle, tenant_name=document.tenant_name,
        columns=document.columns, rows=document.rows, generated_at=document.generated_at,
        row_count=len(document.rows),
    )


@router.get("/export")
def export_report(
    report_type: str, format: str = "xlsx", filters: DashboardFilters = Depends(_filters_dependency),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("reports.export")),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if format not in _EXPORTERS:
        raise ValidationFailedError(f"Formato inválido: {format!r}. Use csv, xlsx ou pdf.")

    document = report_service.build_report(
        db, tenant_id, _tenant_name(db, tenant_id), ReportRequest(report_type, filters),
    )
    content = _EXPORTERS[format](document)
    filename = f"opsflow_{report_type}_{date.today().isoformat()}.{format}"
    return StreamingResponse(
        io.BytesIO(content), media_type=_CONTENT_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
