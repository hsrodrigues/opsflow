"""In-memory session state for the currently logged-in user.

Fase 2 keeps this memory-only: the refresh token never touches disk unless
"Lembrar acesso" is checked, in which case it's handed to
`services/token_store.py` (seção 32/33 will build proper offline/secure
storage on top of this later — see `docs/ARCHITECTURE.md`).
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UserSession:
    access_token: str | None = None
    refresh_token: str | None = None
    access_token_expires_at: datetime | None = None
    user_id: int | None = None
    email: str | None = None
    full_name: str | None = None
    phone: str | None = None
    tenant_id: int | None = None
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    license_status: str | None = None
    license_plan_code: str | None = None
    license_expires_at: datetime | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.access_token is not None

    def has_permission(self, code: str) -> bool:
        return code in self.permissions

    def clear(self) -> None:
        """Reset every field back to its default (used on logout)."""
        self.__init__()
