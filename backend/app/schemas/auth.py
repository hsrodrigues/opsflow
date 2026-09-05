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
    phone: str | None = None
    tenant_id: int | None
    # `None` pra um SUPER_ADMIN (sem tenant) — o desktop mostra "Plataforma"
    # nesse caso. Sem isso, a barra de status só tinha o `tenant_id`
    # numérico pra exibir ("Empresa #1"), nunca o nome de verdade da
    # empresa — bug real reportado pelo usuário.
    tenant_name: str | None = None
    roles: list[str]
    permissions: list[str]


class MyProfileUpdate(BaseModel):
    """`PATCH /auth/me` — auto-atendimento (seção 26 "Configurações"):
    qualquer usuário autenticado pode editar o próprio nome/telefone, sem
    depender da permissão `users.manage` que só admins têm. Não inclui senha
    de propósito — trocar senha continua uma ação exclusiva do admin da
    empresa, na tela Usuários (nunca havia um fluxo de "esqueci minha senha"
    self-service, e a decisão foi não criar um)."""

    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserInfo
    license: LicenseInfo | None = None
