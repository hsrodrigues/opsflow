"""Request/response schemas for `/api/v1/schedules` (seção 13)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import ScheduleStatus, UnitOfMeasure

Shift = Literal["MANHA", "TARDE", "NOITE"]


class ScheduleItemCreate(BaseModel):
    schedule_date: date
    shift: Shift
    route_id: int
    carrier_id: int | None = None
    vehicle_id: int | None = None
    driver_id: int | None = None
    product_id: int | None = None
    scheduled_at: datetime
    cargo_description: str | None = Field(default=None, max_length=255)
    quantity: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)


class ScheduleItemUpdate(BaseModel):
    route_id: int | None = None
    carrier_id: int | None = None
    vehicle_id: int | None = None
    driver_id: int | None = None
    product_id: int | None = None
    scheduled_at: datetime | None = None
    cargo_description: str | None = Field(default=None, max_length=255)
    quantity: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)


class StatusChangeRequest(BaseModel):
    status: ScheduleStatus
    notes: str | None = Field(default=None, max_length=500)


class DuplicateScheduleRequest(BaseModel):
    source_date: date
    target_date: date


class DuplicateScheduleResult(BaseModel):
    items_created: int


class ScheduleItemOut(BaseModel):
    id: int
    schedule_date: date
    shift: str
    route_name: str
    carrier_name: str | None
    vehicle_plate: str | None
    driver_name: str | None
    product_name: str | None
    unit_of_measure: UnitOfMeasure | None
    scheduled_at: datetime
    cargo_description: str | None
    quantity: float | None
    notes: str | None
    status: ScheduleStatus
    operation_number: str | None


class StatusHistoryOut(BaseModel):
    previous_status: ScheduleStatus | None
    new_status: ScheduleStatus
    changed_at: datetime
    notes: str | None
