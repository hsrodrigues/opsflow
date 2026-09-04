"""User repository.

`get_user_by_email` is deliberately **not** tenant-scoped: at login time the
caller does not know the tenant yet — discovering it *is* the point of the
lookup (a user's `tenant_id` comes from the row itself; `SUPER_ADMIN` users
have none at all). Every other user operation, once a session is
authenticated, goes through `UserRepository`, which is tenant-scoped like
every other `TenantRepository`.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.role import Role
from app.models.user import User
from app.repositories.base import TenantRepository


def get_user_by_email(db: Session, email: str) -> User | None:
    """Look up a user by e-mail across all tenants (and platform SUPER_ADMINs).

    Used exclusively by the login flow. Eagerly loads `roles` (and their
    `permissions`) because the login response needs them immediately, and a
    detached ORM instance can't lazy-load after the request's session closes.
    """
    normalized_email = email.strip().lower()
    stmt = (
        select(User)
        .where(User.email == normalized_email)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    return db.execute(stmt).scalar_one_or_none()


class UserRepository(TenantRepository[User]):
    """Tenant-scoped user operations, for use once a request is authenticated."""

    model = User
