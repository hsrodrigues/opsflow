"""Declarative base class and reusable mixins for all OpsFlow ORM models."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for every ORM model in the application."""

    pass


class TimestampMixin:
    """Adds `created_at` / `updated_at` timestamps, managed by the database."""

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    """Adds a nullable `deleted_at` column for soft-delete support."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)


class TenantMixin:
    """Adds the `tenant_id` column used to isolate every business table.

    Every table that carries this mixin MUST be filtered by `tenant_id` in
    every query issued by the repository layer — this is the single
    mechanism that guarantees one company can never see another company's
    data. See `app/repositories/base.py` (Fase 2) for the enforcement point.
    """

    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )


class AuditMixin:
    """Adds `created_by` / `updated_by` references to the acting user."""

    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
