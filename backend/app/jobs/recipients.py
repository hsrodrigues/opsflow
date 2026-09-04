"""Shared helper: who a background job should notify for a given tenant.

ADMIN_EMPRESA and SUPERVISOR are the roles seção 4 describes as tracking
the operation day-to-day — the ones a "🔴 Operação atrasada" or "⚠ CNH
vencendo" alert is actually for.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserStatus
from app.models.role import Role
from app.models.user import User, user_roles

_RECIPIENT_ROLE_CODES = ("ADMIN_EMPRESA", "SUPERVISOR")


def recipients_for_tenant(db: Session, tenant_id: int) -> list[User]:
    stmt = (
        select(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(
            User.tenant_id == tenant_id, User.status == UserStatus.ATIVO,
            Role.code.in_(_RECIPIENT_ROLE_CODES),
        )
        .distinct()
    )
    return list(db.execute(stmt).scalars().all())
