"""Request/response schemas for `/api/v1/products`."""
from pydantic import BaseModel, Field

from app.models.enums import ProductStatus, UnitOfMeasure


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=50)
    unit_of_measure: UnitOfMeasure = UnitOfMeasure.UNIDADE
    default_weight_kg: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=50)
    unit_of_measure: UnitOfMeasure | None = None
    default_weight_kg: float | None = Field(default=None, ge=0)
    status: ProductStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ProductOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    sku: str | None
    unit_of_measure: UnitOfMeasure
    default_weight_kg: float | None
    status: ProductStatus
    notes: str | None
