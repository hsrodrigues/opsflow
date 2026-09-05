"""Panel service — dados do painel de operações somente-leitura pensado
para ficar numa TV do centro de operações (sem rastreador/GPS: mostra só de
onde para onde cada carga está indo e em que status está, atualizando
conforme os status mudam no sistema).

O acesso é por posse de um `panel_token` opaco (gerado sob demanda, nunca
escolhido pelo cliente) em vez de login — uma TV não tem teclado/2FA, então
funciona como um link de compartilhamento: quem tem o link vê o quadro
daquele tenant, só leitura, sem nenhum dado sensível (sem CPF, sem preços,
sem dados de outros tenants). Regenerar o token invalida o link antigo.
"""
import secrets
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import ScheduleStatus
from app.models.tenant import Tenant
from app.repositories.schedule_repository import ScheduleItemRepository
from app.schemas.panel import PanelBoardOut, PanelOperationOut, PanelPointOut, PanelSummaryOut

_WAITING_STATUSES = (ScheduleStatus.PROGRAMADO, ScheduleStatus.AGUARDANDO, ScheduleStatus.EM_FILA)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_or_create_panel_token(db: Session, tenant_id: int) -> str:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Empresa não encontrada.")
    if not tenant.panel_token:
        tenant.panel_token = secrets.token_urlsafe(24)
        db.commit()
    return tenant.panel_token


def regenerate_panel_token(db: Session, tenant_id: int) -> str:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Empresa não encontrada.")
    tenant.panel_token = secrets.token_urlsafe(24)
    db.commit()
    return tenant.panel_token


def resolve_tenant_by_token(db: Session, token: str) -> Tenant:
    tenant = db.execute(select(Tenant).where(Tenant.panel_token == token)).scalar_one_or_none()
    if tenant is None:
        raise NotFoundError("Painel não encontrado. O link pode ter sido renovado — peça um novo link ao admin.")
    return tenant


def _point(location) -> PanelPointOut:
    return PanelPointOut(name=location.name, latitude=location.latitude, longitude=location.longitude)


def get_board(db: Session, tenant: Tenant) -> PanelBoardOut:
    today = date.today()
    items, _ = ScheduleItemRepository(db, tenant.id).search(schedule_date=today, limit=200, offset=0)
    items = [item for item in items if item.status != ScheduleStatus.CANCELADO]
    items.sort(key=lambda item: item.scheduled_at)

    operations = [
        PanelOperationOut(
            operation_number=item.operation.operation_number if item.operation else None,
            route_name=item.route.name,
            origin=_point(item.route.origin),
            destination=_point(item.route.destination),
            carrier_name=item.carrier.legal_name if item.carrier else None,
            vehicle_plate=item.vehicle.plate if item.vehicle else None,
            driver_name=item.driver.full_name if item.driver else None,
            cargo_description=item.cargo_description,
            status=item.status,
            scheduled_at=item.scheduled_at,
            started_at=item.operation.started_at if item.operation else None,
            completed_at=item.operation.completed_at if item.operation else None,
        )
        for item in items
    ]

    summary = PanelSummaryOut(
        em_operacao=sum(1 for i in items if i.status == ScheduleStatus.EM_OPERACAO),
        aguardando=sum(1 for i in items if i.status in _WAITING_STATUSES),
        atrasado=sum(1 for i in items if i.status == ScheduleStatus.ATRASADO),
        concluido_hoje=sum(1 for i in items if i.status == ScheduleStatus.CONCLUIDO),
    )

    return PanelBoardOut(
        tenant_name=tenant.trade_name or tenant.legal_name,
        generated_at=_utc_now(),
        summary=summary,
        operations=operations,
    )
