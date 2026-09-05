"""`/api/v1/license` — plano, status e uso atual da empresa (seção 6/7).

Sem `manage`: gestão de licença (renovar, trocar de plano) é uma operação
de plataforma (`SUPER_ADMIN`), fora do escopo de qualquer tenant — esta
rota é só leitura, pra empresa acompanhar seu próprio consumo.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.user import User
from app.schemas.license import LicenseSummary
from app.services import license_service

router = APIRouter(prefix="/license", tags=["license"])


@router.get("", response_model=LicenseSummary)
def get_license(
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("dashboard.view")),
    db: Session = Depends(get_db),
) -> LicenseSummary:
    return license_service.build_license_summary(db, tenant_id)
