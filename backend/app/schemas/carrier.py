"""Request/response schemas for `/api/v1/carriers` (seção 11)."""
from pydantic import BaseModel, Field

from app.models.enums import CarrierStatus


class CarrierCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    cnpj: str | None = Field(default=None, max_length=18)
    contact_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)


class CarrierUpdate(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    cnpj: str | None = Field(default=None, max_length=18)
    contact_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    status: CarrierStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)


class CarrierOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    legal_name: str
    trade_name: str | None
    cnpj: str | None
    contact_name: str | None
    phone: str | None
    email: str | None
    status: CarrierStatus
    notes: str | None
