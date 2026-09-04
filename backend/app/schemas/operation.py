"""Response schemas for `/api/v1/operations` — Centro de Operações (seção 21)."""
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ScheduleStatus


class OperationOut(BaseModel):
    id: int
    operation_number: str
    schedule_item_id: int
    route_name: str
    vehicle_plate: str | None
    carrier_name: str | None
    driver_name: str | None
    status: ScheduleStatus
    scheduled_at: datetime
    arrived_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None


class OperationsSummary(BaseModel):
    programadas: int
    em_operacao: int
    atrasadas: int
