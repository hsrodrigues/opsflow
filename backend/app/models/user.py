"""User model and role assignment (seção 4/5).

`tenant_id` is nullable **only** for `SUPER_ADMIN` accounts: they are
platform-level operators (seção 54), not employees of a customer company.
Every other role must have a `tenant_id`, enforced in the service layer
(Fase 2) rather than at the schema level, since the same `users` table must
support both cases.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import UserStatus
from app.models.types import bigint_pk, enum_column

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    # Denormalizado a partir de users.tenant_id: reforça o isolamento por
    # tenant também nas junções de RBAC, permitindo auditar/filtrar
    # atribuições de papel sem precisar de um JOIN adicional em users.
    Column("tenant_id", BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
)


class User(Base, TimestampMixin):
    """An OpsFlow user: a platform SUPER_ADMIN or an employee of a tenant."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        enum_column(UserStatus, length=20), default=UserStatus.ATIVO, nullable=False
    )
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remember_login: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tenant: Mapped["Tenant"] = relationship()
    roles: Mapped[list["Role"]] = relationship(secondary=user_roles)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} email={self.email!r}>"
