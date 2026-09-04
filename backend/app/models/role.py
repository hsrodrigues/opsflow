"""RBAC: role and permission models (seção 4).

Roles are global reference data (the 5 fixed profiles from the spec:
SUPER_ADMIN, ADMIN_EMPRESA, SUPERVISOR, OPERADOR, VISUALIZADOR), seeded by
the initial migration rather than created through the app — they are not
tenant-specific. A user's tenant comes from `User.tenant_id`; their role(s)
come from `user_roles`.
"""
from sqlalchemy import BigInteger, ForeignKey, String, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import UserRoleCode
from app.models.types import bigint_pk, enum_column

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    """A fixed RBAC profile (seção 4). Reference data, not tenant-scoped."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    code: Mapped[UserRoleCode] = mapped_column(enum_column(UserRoleCode, length=20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    permissions: Mapped[list["Permission"]] = relationship(secondary=role_permissions, back_populates="roles")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Role id={self.id} code={self.code}>"


class Permission(Base):
    """A single, fine-grained action a role may be granted (e.g. `vehicles.create`)."""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    roles: Mapped[list["Role"]] = relationship(secondary=role_permissions, back_populates="permissions")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Permission id={self.id} code={self.code!r}>"
