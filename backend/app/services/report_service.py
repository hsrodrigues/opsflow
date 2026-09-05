"""Report service (seção 17): monta um `ReportDocument` para cada tipo de
relatório, reaproveitando ao máximo o que já existe — os mesmos filtros e
consultas do dashboard (`apply_schedule_filters`/`DashboardFilters`) para
Operações e Transportadoras, e os mesmos repositories das telas de cadastro
para Veículos — em vez de reescrever consultas equivalentes do zero. Isso
garante que um relatório sempre bate com o que a tela correspondente já
mostra para o mesmo período/filtro.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationFailedError
from app.models.carrier import Carrier
from app.models.driver import Driver
from app.models.enums import OccurrenceSeverity, OccurrenceStatus, ScheduleStatus
from app.models.operation import Operation
from app.models.route import Route
from app.models.schedule import Schedule, ScheduleItem
from app.models.vehicle import Vehicle
from app.repositories.carrier_repository import CarrierRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.services import occurrence_service
from app.services.dashboard_service import DashboardFilters, apply_schedule_filters
from app.services.export_service import ReportDocument

REPORT_TYPES = ("operacoes", "ocorrencias", "veiculos", "transportadoras")

_STATUS_LABELS = {
    "PROGRAMADO": "Programado", "AGUARDANDO": "Aguardando", "EM_FILA": "Em fila",
    "EM_OPERACAO": "Em operação", "CONCLUIDO": "Concluído", "ATRASADO": "Atrasado", "CANCELADO": "Cancelado",
}
_SEVERITY_LABELS = {"BAIXA": "Baixa", "MEDIA": "Média", "ALTA": "Alta", "CRITICA": "Crítica"}
_OCCURRENCE_STATUS_LABELS = {
    "ABERTA": "Aberta", "EM_ANALISE": "Em análise", "RESOLVIDA": "Resolvida", "CANCELADA": "Cancelada",
}
_VEHICLE_STATUS_LABELS = {
    "DISPONIVEL": "Disponível", "EM_OPERACAO": "Em operação", "EM_MANUTENCAO": "Em manutenção",
    "INATIVO": "Inativo", "BLOQUEADO": "Bloqueado",
}
_SHIFT_LABELS = {"MANHA": "Manhã", "TARDE": "Tarde", "NOITE": "Noite"}
_MAX_ROWS = 5000  # teto de segurança — um relatório não é a tela paginada


def _label(mapping: dict, value) -> str:
    key = value.value if hasattr(value, "value") else value
    return mapping.get(key, key or "—")


def _period_subtitle(filters: DashboardFilters) -> str:
    if filters.period_start and filters.period_end:
        period = f"Período: {filters.period_start.strftime('%d/%m/%Y')} a {filters.period_end.strftime('%d/%m/%Y')}"
    elif filters.period_start:
        period = f"A partir de {filters.period_start.strftime('%d/%m/%Y')}"
    elif filters.period_end:
        period = f"Até {filters.period_end.strftime('%d/%m/%Y')}"
    else:
        period = "Todo o período"
    extra = []
    if filters.shift:
        extra.append(f"turno {_label(_SHIFT_LABELS, filters.shift)}")
    if filters.status:
        extra.append(f"status {_label(_STATUS_LABELS, filters.status)}")
    if extra:
        period += " · " + ", ".join(extra)
    return period


def _fmt_dt(value: datetime | None) -> str:
    return value.strftime("%d/%m/%Y %H:%M") if value else "—"


def _fmt_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


@dataclass
class ReportRequest:
    report_type: str
    filters: DashboardFilters


def build_report(db: Session, tenant_id: int, tenant_name: str, request: ReportRequest) -> ReportDocument:
    if request.report_type not in REPORT_TYPES:
        raise ValidationFailedError(f"Tipo de relatório inválido: {request.report_type!r}.")
    builder = {
        "operacoes": _build_operations_report,
        "ocorrencias": _build_occurrences_report,
        "veiculos": _build_vehicles_report,
        "transportadoras": _build_carriers_report,
    }[request.report_type]
    return builder(db, tenant_id, tenant_name, request.filters)


def _build_operations_report(db: Session, tenant_id: int, tenant_name: str, filters: DashboardFilters) -> ReportDocument:
    stmt = (
        select(
            Schedule.schedule_date, Schedule.shift, Route.name, Carrier.legal_name, Vehicle.plate,
            Driver.full_name, ScheduleItem.scheduled_at, ScheduleItem.status, Operation.operation_number,
        )
        .select_from(ScheduleItem)
        .join(Route, ScheduleItem.route_id == Route.id)
        .outerjoin(Carrier, ScheduleItem.carrier_id == Carrier.id)
        .outerjoin(Vehicle, ScheduleItem.vehicle_id == Vehicle.id)
        .outerjoin(Driver, ScheduleItem.driver_id == Driver.id)
        .outerjoin(Operation, Operation.schedule_item_id == ScheduleItem.id)
    )
    stmt = apply_schedule_filters(stmt, tenant_id, filters).order_by(Schedule.schedule_date, ScheduleItem.scheduled_at)
    rows = [
        [
            _fmt_date(schedule_date), _label(_SHIFT_LABELS, shift), route_name, carrier_name or "—",
            plate or "—", driver_name or "—", _fmt_dt(scheduled_at), _label(_STATUS_LABELS, status),
            operation_number or "—",
        ]
        for schedule_date, shift, route_name, carrier_name, plate, driver_name, scheduled_at, status,
        operation_number in db.execute(stmt.limit(_MAX_ROWS)).all()
    ]
    return ReportDocument(
        title="Relatório de Operações", subtitle=_period_subtitle(filters), tenant_name=tenant_name,
        columns=["Data", "Turno", "Rota", "Transportadora", "Veículo", "Motorista", "Horário previsto", "Status", "Nº operação"],
        rows=rows,
    )


def _build_occurrences_report(db: Session, tenant_id: int, tenant_name: str, filters: DashboardFilters) -> ReportDocument:
    occurrences, _total = occurrence_service.list_occurrences(
        db, tenant_id, severity=None, status=None,
        start_date=filters.period_start, end_date=filters.period_end, limit=_MAX_ROWS, offset=0,
    )
    rows = [
        [
            _fmt_dt(o.occurred_at), o.occurrence_type.name, o.vehicle.plate if o.vehicle else "—",
            o.driver.full_name if o.driver else "—", _label(_SEVERITY_LABELS, o.severity),
            _label(_OCCURRENCE_STATUS_LABELS, o.status),
            o.responsible_user.full_name if o.responsible_user else "—", o.description,
        ]
        for o in occurrences
    ]
    return ReportDocument(
        title="Relatório de Ocorrências", subtitle=_period_subtitle(filters), tenant_name=tenant_name,
        columns=["Data/Hora", "Tipo", "Veículo", "Motorista", "Severidade", "Status", "Responsável", "Descrição"],
        rows=rows,
    )


def _build_vehicles_report(db: Session, tenant_id: int, tenant_name: str, filters: DashboardFilters) -> ReportDocument:
    vehicles, _total = VehicleRepository(db, tenant_id).search(
        status=filters.status, carrier_id=filters.carrier_id, limit=_MAX_ROWS, offset=0,
    )
    rows = [
        [
            v.plate, v.brand or "—", v.model or "—", str(v.year) if v.year else "—",
            f"{v.capacity:.0f} kg" if v.capacity else "—", v.carrier.legal_name if v.carrier else "—",
            _label(_VEHICLE_STATUS_LABELS, v.status),
        ]
        for v in vehicles
    ]
    return ReportDocument(
        title="Relatório de Veículos", subtitle=_period_subtitle(filters) if filters.period_start or filters.period_end else "Frota atual",
        tenant_name=tenant_name, columns=["Placa", "Marca", "Modelo", "Ano", "Capacidade", "Transportadora", "Status"],
        rows=rows,
    )


def _build_carriers_report(db: Session, tenant_id: int, tenant_name: str, filters: DashboardFilters) -> ReportDocument:
    """Ranking de transportadoras (seção 11): viagens, concluídas, canceladas,
    atrasos, tempo médio e índice de eficiência (% concluídas/total) — cada
    contagem reaproveita o mesmo filtro de período/turno/status do dashboard.
    """
    carriers, _total = CarrierRepository(db, tenant_id).search(limit=_MAX_ROWS, offset=0)

    def _count(carrier_id: int, status: ScheduleStatus | None = None) -> int:
        carrier_filters = DashboardFilters(**{**filters.__dict__, "carrier_id": carrier_id, "status": status})
        stmt = apply_schedule_filters(select(func.count(ScheduleItem.id)), tenant_id, carrier_filters)
        return db.execute(stmt).scalar_one()

    def _avg_duration_minutes(carrier_id: int) -> float | None:
        carrier_filters = DashboardFilters(**{**filters.__dict__, "carrier_id": carrier_id})
        stmt = apply_schedule_filters(
            select(Operation.started_at, Operation.completed_at)
            .join(ScheduleItem, Operation.schedule_item_id == ScheduleItem.id)
            .where(Operation.status == ScheduleStatus.CONCLUIDO, Operation.started_at.is_not(None), Operation.completed_at.is_not(None)),
            tenant_id, carrier_filters, with_status=False,
        )
        durations = [(completed - started).total_seconds() / 60 for started, completed in db.execute(stmt).all()]
        return round(sum(durations) / len(durations), 1) if durations else None

    rows = []
    for carrier in carriers:
        total = _count(carrier.id)
        if total == 0:
            continue  # sem viagens no período — não polui o ranking
        concluidas = _count(carrier.id, ScheduleStatus.CONCLUIDO)
        canceladas = _count(carrier.id, ScheduleStatus.CANCELADO)
        atrasadas = _count(carrier.id, ScheduleStatus.ATRASADO)
        tempo_medio = _avg_duration_minutes(carrier.id)
        eficiencia = round((concluidas / total) * 100, 1)
        rows.append([
            carrier.legal_name, str(total), str(concluidas), str(canceladas), str(atrasadas),
            f"{tempo_medio:.1f} min" if tempo_medio is not None else "—", f"{eficiencia:.1f}%",
        ])
    rows.sort(key=lambda row: float(row[-1].rstrip("%")), reverse=True)

    return ReportDocument(
        title="Ranking de Transportadoras", subtitle=_period_subtitle(filters), tenant_name=tenant_name,
        columns=["Transportadora", "Viagens", "Concluídas", "Canceladas", "Atrasos", "Tempo médio", "Eficiência"],
        rows=rows,
    )
