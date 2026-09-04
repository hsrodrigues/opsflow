"""Response schemas for `/api/v1/dashboard` (seção 15/16)."""
from pydantic import BaseModel


class DashboardSummary(BaseModel):
    """KPIs do topo do dashboard (seção 15) — cálculos documentados na seção 16."""

    operacoes_hoje: int
    concluidas: int
    em_andamento: int
    atrasadas: int
    canceladas: int
    veiculos_ativos: int
    ocorrencias: int
    tempo_medio_minutos: float | None
    taxa_conclusao_percentual: float
    indice_atraso_percentual: float


class ChartPoint(BaseModel):
    label: str
    value: float


class DashboardCharts(BaseModel):
    operacoes_por_dia: list[ChartPoint]
    operacoes_por_transportadora: list[ChartPoint]
    operacoes_por_status: list[ChartPoint]
    ocorrencias_por_severidade: list[ChartPoint]
