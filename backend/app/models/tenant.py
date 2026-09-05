"""Tenant (empresa cliente) model.

A `Tenant` is the top-level isolation boundary of the whole application:
every business table carries a `tenant_id` (via `TenantMixin`) that must
always be filtered by the repository layer, so that one company's data is
never visible to another (see `app/models/base.py` and Fase 2's repository
enforcement).
"""
from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.types import bigint_pk


class Tenant(Base, TimestampMixin):
    """A company using OpsFlow. Owns users, vehicles, operations, etc."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(18), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Token opaco do painel de TV somente-leitura (seção "painel de
    # operações") — gerado sob demanda, nunca escolhido pelo cliente; `None`
    # até a empresa gerar seu primeiro link. Ver a migration que o introduz
    # para o raciocínio completo de por que não é uma sessão JWT normal.
    panel_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="tenant")
    licenses: Mapped[list["License"]] = relationship(back_populates="tenant")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Tenant id={self.id} legal_name={self.legal_name!r}>"
