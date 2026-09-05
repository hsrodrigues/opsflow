"""Request/response schemas for `/api/v1/routes` (seção 12).

Origin/destination are plain names in the API — the underlying `Location`
rows they resolve to (see `location_repository.get_or_create_location`) are
an implementation detail, not something the caller manages directly. As
exceção são as coordenadas: totalmente opcionais, existem só para alimentar
o mapa do Painel de operações (TV) — uma rota sem elas continua funcionando
normalmente em todo o resto do sistema, só não aparece no mapa.
"""
from pydantic import BaseModel, Field

from app.models.enums import RouteStatus


class RouteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    origin_name: str = Field(min_length=1, max_length=150)
    destination_name: str = Field(min_length=1, max_length=150)
    origin_latitude: float | None = Field(default=None, ge=-90, le=90)
    origin_longitude: float | None = Field(default=None, ge=-180, le=180)
    destination_latitude: float | None = Field(default=None, ge=-90, le=90)
    destination_longitude: float | None = Field(default=None, ge=-180, le=180)
    distance_km: float | None = Field(default=None, ge=0)
    estimated_time_minutes: int | None = Field(default=None, ge=0)
    operation_type: str | None = Field(default=None, max_length=50)


class RouteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    origin_name: str | None = Field(default=None, min_length=1, max_length=150)
    destination_name: str | None = Field(default=None, min_length=1, max_length=150)
    origin_latitude: float | None = Field(default=None, ge=-90, le=90)
    origin_longitude: float | None = Field(default=None, ge=-180, le=180)
    destination_latitude: float | None = Field(default=None, ge=-90, le=90)
    destination_longitude: float | None = Field(default=None, ge=-180, le=180)
    distance_km: float | None = Field(default=None, ge=0)
    estimated_time_minutes: int | None = Field(default=None, ge=0)
    operation_type: str | None = Field(default=None, max_length=50)
    status: RouteStatus | None = None


class RouteOut(BaseModel):
    id: int
    name: str
    origin_name: str
    destination_name: str
    origin_latitude: float | None
    origin_longitude: float | None
    destination_latitude: float | None
    destination_longitude: float | None
    distance_km: float | None
    estimated_time_minutes: int | None
    operation_type: str | None
    status: RouteStatus
