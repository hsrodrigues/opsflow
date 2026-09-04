"""Request/response schemas for `/api/v1/auth` (seção 5/6)."""
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# Validação de formato deliberadamente permissiva: `pydantic.EmailStr` usa
# `email_validator` com os defaults, que rejeita TLDs "special-use" como
# `.local`/`.test`/`.internal` (RFC 6761) — exatamente o domínio que a
# própria seção 38 do documento de especificação usa para o usuário demo
# (`admin@opsflow.local`). Um ambiente on-premise/demo legitimamente usa
# esses domínios, então validamos só a forma geral `algo@algo.algo`.
EmailAddress = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)]


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=200)
    remember: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class LicenseInfo(BaseModel):
    status: str
    plan_code: str
    expires_at: datetime | None
    max_users: int | None
    max_vehicles: int | None


class UserInfo(BaseModel):
    id: int
    email: str
    full_name: str
    tenant_id: int | None
    roles: list[str]
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserInfo
    license: LicenseInfo | None = None
