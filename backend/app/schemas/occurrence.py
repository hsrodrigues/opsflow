"""Request/response schemas for `/api/v1/occurrences` (seção 14).

`occurrence_type_name` is a plain name, resolved/created behind the scenes
(same find-or-create pattern as `Route`'s origin/destination) — there is no
separate "tipos de ocorrência" screen, per the model's own "tenant-
configurable" design.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import OccurrenceSeverity, OccurrenceStatus


class OccurrenceCreate(BaseModel):
    occurrence_type_name: str = Field(min_length=1, max_length=100)
    vehicle_id: int | None = None
    driver_id: int | None = None
    description: str = Field(min_length=1)
    severity: OccurrenceSeverity = OccurrenceSeverity.BAIXA
    occurred_at: datetime


class OccurrenceUpdate(BaseModel):
    occurrence_type_name: str | None = Field(default=None, min_length=1, max_length=100)
    vehicle_id: int | None = None
    driver_id: int | None = None
    description: str | None = Field(default=None, min_length=1)
    severity: OccurrenceSeverity | None = None
    status: OccurrenceStatus | None = None
    occurred_at: datetime | None = None


class OccurrenceOut(BaseModel):
    id: int
    occurrence_type_name: str
    vehicle_plate: str | None
    driver_name: str | None
    responsible_user_name: str | None
    description: str
    severity: OccurrenceSeverity
    status: OccurrenceStatus
    occurred_at: datetime
