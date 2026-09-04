"""Request/response schemas for `/api/v1/drivers` (seção 10)."""
from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import DriverStatus


class DriverCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    cpf: str = Field(min_length=1, max_length=14)
    cnh_number: str | None = Field(default=None, max_length=20)
    cnh_category: str | None = Field(default=None, max_length=5)
    cnh_expiry: date | None = None
    phone: str | None = Field(default=None, max_length=30)
    carrier_id: int | None = None


class DriverUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    cpf: str | None = Field(default=None, min_length=1, max_length=14)
    cnh_number: str | None = Field(default=None, max_length=20)
    cnh_category: str | None = Field(default=None, max_length=5)
    cnh_expiry: date | None = None
    phone: str | None = Field(default=None, max_length=30)
    carrier_id: int | None = None
    status: DriverStatus | None = None


class DriverOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    full_name: str
    cpf: str
    cnh_number: str | None
    cnh_category: str | None
    cnh_expiry: date | None
    phone: str | None
    carrier_id: int | None
    status: DriverStatus
