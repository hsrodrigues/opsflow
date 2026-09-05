"""Schemas for `/api/v1/platform` — gestão de empresas clientes e suas
licenças por um `SUPER_ADMIN` (seção 54). Nunca usado por uma empresa
cliente; `TenantCreate` faz onboarding completo (empresa + licença TRIAL +
primeiro `ADMIN_EMPRESA`) numa única chamada porque é assim que esse
fluxo acontece de verdade — ninguém cria uma empresa sem ninguém pra
administrá-la.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import LicenseStatus, PlanCode
from app.schemas.auth import EmailAddress


class TenantCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    cnpj: str | None = Field(default=None, max_length=18)
    plan_code: PlanCode = PlanCode.STARTER
    trial_days: int = Field(default=30, ge=1, le=365)
    admin_email: EmailAddress
    admin_full_name: str = Field(min_length=1, max_length=200)
    admin_password: str = Field(min_length=8, max_length=100)


class TenantUpdate(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class TenantLicenseUpdate(BaseModel):
    plan_code: PlanCode | None = None
    status: LicenseStatus | None = None
    expires_at: datetime | None = None
    max_users: int | None = Field(default=None, ge=1)
    max_vehicles: int | None = Field(default=None, ge=1)


class LicenseKeyCreate(BaseModel):
    plan_code: PlanCode = PlanCode.STARTER
    trial_days: int = Field(default=30, ge=1, le=365)


class LicenseKeyOut(BaseModel):
    id: int
    license_key: str
    plan_code: str
    pending_trial_days: int | None
    issued_at: datetime
    activated_at: datetime | None
    tenant_id: int | None
    tenant_name: str | None


class ArchiveRequest(BaseModel):
    older_than_months: int = Field(default=12, ge=1, le=120)


class ArchiveResult(BaseModel):
    operations_archived: int
    occurrences_archived: int


class BackupOut(BaseModel):
    filename: str
    size_bytes: int
    created_at: datetime


class BackupRestoreRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=100)


class TenantOut(BaseModel):
    id: int
    legal_name: str
    trade_name: str | None
    cnpj: str | None
    is_active: bool
    created_at: datetime
    license_key: str | None
    plan_code: str | None
    license_status: str | None
    license_expires_at: datetime | None
    max_users: int | None
    max_vehicles: int | None
    user_count: int
    vehicle_count: int
