"""Response schema for `/api/v1/license` — o mesmo `LicenseInfo` do login
(seção 6) mais o uso atual (contagem real de usuários/veículos), pra tela
poder mostrar "X de Y" em vez de só o limite."""
from datetime import datetime

from pydantic import BaseModel


class LicenseSummary(BaseModel):
    # Sem `license_key` de propósito: é o código de ativação (seção 6),
    # gerado e visível só pra quem opera a plataforma (`SUPER_ADMIN`, ver
    # `TenantOut` em `schemas/platform.py`) — a própria empresa nunca
    # precisa vê-lo ou regenerá-lo, só usar o sistema já ativado.
    plan_code: str
    plan_name: str
    status: str
    issued_at: datetime
    expires_at: datetime | None
    max_users: int | None
    max_vehicles: int | None
    current_users: int
    current_vehicles: int
