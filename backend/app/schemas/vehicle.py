"""Request/response schemas for `/api/v1/vehicles` (seção 9)."""
from pydantic import BaseModel, Field

from app.models.enums import VehicleStatus


class VehicleCreate(BaseModel):
    plate: str = Field(min_length=1, max_length=10)
    renavam: str | None = Field(default=None, max_length=20)
    vehicle_type_id: int | None = None
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2100)
    carrier_id: int | None = None
    capacity: float | None = Field(default=None, ge=0)
    current_driver_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


class VehicleUpdate(BaseModel):
    plate: str | None = Field(default=None, min_length=1, max_length=10)
    renavam: str | None = Field(default=None, max_length=20)
    vehicle_type_id: int | None = None
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2100)
    carrier_id: int | None = None
    capacity: float | None = Field(default=None, ge=0)
    status: VehicleStatus | None = None
    current_driver_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


class VehicleOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    plate: str
    renavam: str | None
    vehicle_type_id: int | None
    brand: str | None
    model: str | None
    year: int | None
    carrier_id: int | None
    capacity: float | None
    status: VehicleStatus
    current_driver_id: int | None
    notes: str | None
