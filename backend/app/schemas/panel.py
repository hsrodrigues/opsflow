"""Schemas for `/api/v1/panel` — o painel de operações somente-leitura
pensado para ficar numa TV do centro de operações. Mostra pra onde cada
carga está indo e em que status está, sem depender de rastreador/GPS."""
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ScheduleStatus


class PanelPointOut(BaseModel):
    name: str
    latitude: float | None
    longitude: float | None


class PanelOperationOut(BaseModel):
    operation_number: str | None
    route_name: str
    origin: PanelPointOut
    destination: PanelPointOut
    carrier_name: str | None
    vehicle_plate: str | None
    driver_name: str | None
    cargo_description: str | None
    status: ScheduleStatus
    scheduled_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class PanelSummaryOut(BaseModel):
    em_operacao: int
    aguardando: int
    atrasado: int
    concluido_hoje: int


class PanelBoardOut(BaseModel):
    tenant_name: str
    generated_at: datetime
    summary: PanelSummaryOut
    operations: list[PanelOperationOut]


class PanelTokenOut(BaseModel):
    token: str
    board_path: str
