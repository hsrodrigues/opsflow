"""Dashboard service — KPIs (seção 16) e dados para os gráficos (seção 15).

Every query here accepts the same set of filters (período, transportadora,
veículo, rota, status, turno — seção 15) so the summary cards and every
chart always reflect the exact same slice of data the user selected.
"""
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.carrier import Carrier
from app.models.enums import ScheduleStatus, VehicleStatus
from app.models.occurrence import Occurrence
from app.models.operation import Operation
from app.models.schedule import Schedule, ScheduleItem
from app.models.vehicle import Vehicle
from app.schemas.dashboard import ChartPoint, DashboardCharts, DashboardSummary


@dataclass
class DashboardFilters:
    period_start: date | None = None
    period_end: date | None = None
    carrier_id: int | None = None
    vehicle_id: int | None = None
    route_id: int | None = None
    status: str | None = None
    shift: str | None = None


def apply_schedule_filters(stmt, tenant_id: int, filters: DashboardFilters, *, with_status: bool = True):
    stmt = (
        stmt.join(Schedule, ScheduleItem.schedule_id == Schedule.id)
        .where(ScheduleItem.tenant_id == tenant_id, ScheduleItem.deleted_at.is_(None))
    )
    if filters.period_start:
        stmt = stmt.where(Schedule.schedule_date >= filters.period_start)
    if filters.period_end:
        stmt = stmt.where(Schedule.schedule_date <= filters.period_end)
    if filters.carrier_id:
        stmt = stmt.where(ScheduleItem.carrier_id == filters.carrier_id)
    if filters.vehicle_id:
        stmt = stmt.where(ScheduleItem.vehicle_id == filters.vehicle_id)
    if filters.route_id:
        stmt = stmt.where(ScheduleItem.route_id == filters.route_id)
    if filters.shift:
        stmt = stmt.where(Schedule.shift == filters.shift)
    if with_status and filters.status:
        stmt = stmt.where(ScheduleItem.status == filters.status)
    return stmt


def _default_filters(filters: DashboardFilters) -> DashboardFilters:
    """Sem período informado, o resumo é sempre 'hoje' (seção 15: "Operações hoje")."""
    if filters.period_start is None and filters.period_end is None:
        today = datetime.now(timezone.utc).date()
        return replace(filters, period_start=today, period_end=today)
    return filters


def get_summary(db: Session, tenant_id: int, filters: DashboardFilters) -> DashboardSummary:
    filters = _default_filters(filters)

    total_stmt = apply_schedule_filters(select(func.count(ScheduleItem.id)), tenant_id, filters, with_status=False)
    total = db.execute(total_stmt).scalar_one()

    def _count_by_status(status: ScheduleStatus) -> int:
        stmt = apply_schedule_filters(select(func.count(ScheduleItem.id)), tenant_id, filters, with_status=False)
        stmt = stmt.where(ScheduleItem.status == status)
        return db.execute(stmt).scalar_one()

    concluidas = _count_by_status(ScheduleStatus.CONCLUIDO)
    em_andamento = _count_by_status(ScheduleStatus.EM_OPERACAO)
    atrasadas = _count_by_status(ScheduleStatus.ATRASADO)
    canceladas = _count_by_status(ScheduleStatus.CANCELADO)

    veiculos_ativos_stmt = select(func.count(Vehicle.id)).where(
        Vehicle.tenant_id == tenant_id, Vehicle.deleted_at.is_(None),
        Vehicle.status.in_((VehicleStatus.DISPONIVEL, VehicleStatus.EM_OPERACAO)),
    )
    veiculos_ativos = db.execute(veiculos_ativos_stmt).scalar_one()

    occurrences_stmt = select(func.count(Occurrence.id)).where(
        Occurrence.tenant_id == tenant_id, Occurrence.deleted_at.is_(None),
    )
    if filters.period_start:
        occurrences_stmt = occurrences_stmt.where(Occurrence.occurred_at >= filters.period_start)
    if filters.period_end:
        occurrences_stmt = occurrences_stmt.where(Occurrence.occurred_at < filters.period_end + timedelta(days=1))
    ocorrencias = db.execute(occurrences_stmt).scalar_one()

    # Tempo médio de operação (seção 16): calculado em Python a partir dos pares
    # started_at/completed_at, não via SQL — MySQL e SQLite (usado nos testes)
    # não compartilham uma função de diferença de datetime portável.
    duration_rows_stmt = (
        select(Operation.started_at, Operation.completed_at)
        .join(ScheduleItem, Operation.schedule_item_id == ScheduleItem.id)
        .where(
            Operation.tenant_id == tenant_id, Operation.status == ScheduleStatus.CONCLUIDO,
            Operation.started_at.is_not(None), Operation.completed_at.is_not(None),
        )
    )
    # `apply_schedule_filters` já faz o JOIN com `Schedule` — não duplicar aqui.
    duration_rows_stmt = apply_schedule_filters(duration_rows_stmt, tenant_id, filters, with_status=False)
    durations = [
        (completed - started).total_seconds() / 60
        for started, completed in db.execute(duration_rows_stmt).all()
    ]
    tempo_medio_minutos = round(sum(durations) / len(durations), 1) if durations else None

    operacoes_hoje_stmt = select(func.count(ScheduleItem.id)).select_from(ScheduleItem).join(
        Schedule, ScheduleItem.schedule_id == Schedule.id
    ).where(
        ScheduleItem.tenant_id == tenant_id, ScheduleItem.deleted_at.is_(None),
        Schedule.schedule_date == datetime.now(timezone.utc).date(),
    )
    operacoes_hoje = db.execute(operacoes_hoje_stmt).scalar_one()

    taxa_conclusao = round((concluidas / total) * 100, 1) if total else 0.0
    indice_atraso = round((atrasadas / total) * 100, 1) if total else 0.0

    return DashboardSummary(
        operacoes_hoje=operacoes_hoje, concluidas=concluidas, em_andamento=em_andamento, atrasadas=atrasadas,
        canceladas=canceladas, veiculos_ativos=veiculos_ativos, ocorrencias=ocorrencias,
        tempo_medio_minutos=tempo_medio_minutos, taxa_conclusao_percentual=taxa_conclusao,
        indice_atraso_percentual=indice_atraso,
    )


def get_charts(db: Session, tenant_id: int, filters: DashboardFilters) -> DashboardCharts:
    filters = _default_filters(filters)

    por_dia_stmt = apply_schedule_filters(
        select(Schedule.schedule_date, func.count(ScheduleItem.id)), tenant_id, filters, with_status=False,
    ).group_by(Schedule.schedule_date).order_by(Schedule.schedule_date)
    operacoes_por_dia = [
        ChartPoint(label=str(day), value=count) for day, count in db.execute(por_dia_stmt).all()
    ]

    por_transportadora_stmt = apply_schedule_filters(
        select(Carrier.legal_name, func.count(ScheduleItem.id))
        .select_from(ScheduleItem)
        .join(Carrier, ScheduleItem.carrier_id == Carrier.id),
        tenant_id, filters, with_status=False,
    ).group_by(Carrier.legal_name).order_by(func.count(ScheduleItem.id).desc()).limit(10)
    operacoes_por_transportadora = [
        ChartPoint(label=name, value=count) for name, count in db.execute(por_transportadora_stmt).all()
    ]

    por_status_stmt = apply_schedule_filters(
        select(ScheduleItem.status, func.count(ScheduleItem.id)), tenant_id, filters, with_status=False,
    ).group_by(ScheduleItem.status)
    operacoes_por_status = [
        ChartPoint(label=status.value if hasattr(status, "value") else status, value=count)
        for status, count in db.execute(por_status_stmt).all()
    ]

    occurrences_stmt = (
        select(Occurrence.severity, func.count(Occurrence.id))
        .where(Occurrence.tenant_id == tenant_id, Occurrence.deleted_at.is_(None))
    )
    if filters.period_start:
        occurrences_stmt = occurrences_stmt.where(Occurrence.occurred_at >= filters.period_start)
    if filters.period_end:
        occurrences_stmt = occurrences_stmt.where(Occurrence.occurred_at < filters.period_end + timedelta(days=1))
    occurrences_stmt = occurrences_stmt.group_by(Occurrence.severity)
    ocorrencias_por_severidade = [
        ChartPoint(label=severity.value if hasattr(severity, "value") else severity, value=count)
        for severity, count in db.execute(occurrences_stmt).all()
    ]

    return DashboardCharts(
        operacoes_por_dia=operacoes_por_dia, operacoes_por_transportadora=operacoes_por_transportadora,
        operacoes_por_status=operacoes_por_status, ocorrencias_por_severidade=ocorrencias_por_severidade,
    )
