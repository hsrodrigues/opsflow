"""Base repository — the single enforcement point for tenant isolation.

Every repository for a tenant-scoped entity should extend `TenantRepository`
instead of querying `Session` directly. `tenant_id` is bound once, in
`__init__`, from the authenticated request (see `app/api/deps.py`) — never
passed per-call — so it is structurally impossible for a query built through
this class to "forget" the filter (seção 3/52/53). Models with
`SoftDeleteMixin` are also automatically excluded once deleted — a repository
subclass never needs to remember to add `deleted_at IS NULL` itself.
"""
from datetime import datetime, timezone
from typing import Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class TenantRepository(Generic[ModelType]):
    """Base repository for a model that carries `tenant_id` (`TenantMixin`)."""

    model: type[ModelType]

    def __init__(self, db: Session, tenant_id: int) -> None:
        if tenant_id is None:
            raise ValueError(
                "TenantRepository requer um tenant_id — use um repositório de plataforma "
                "explícito (sem filtro de tenant) para operações de SUPER_ADMIN."
            )
        self.db = db
        self.tenant_id = tenant_id

    def _base_query(self) -> Select:
        stmt = select(self.model).where(self.model.tenant_id == self.tenant_id)
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt

    def get(self, record_id: int) -> ModelType | None:
        return self.db.execute(self._base_query().where(self.model.id == record_id)).scalar_one_or_none()

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelType]:
        query = self._base_query().limit(limit).offset(offset)
        return list(self.db.execute(query).scalars().all())

    def count(self) -> int:
        stmt = select(func.count()).select_from(self._base_query().subquery())
        return self.db.execute(stmt).scalar_one()

    def add(self, instance: ModelType) -> ModelType:
        if getattr(instance, "tenant_id", None) != self.tenant_id:
            raise ValueError("Tentativa de persistir um registro com tenant_id diferente do repositório.")
        self.db.add(instance)
        self.db.flush()
        return instance

    def soft_delete(self, instance: ModelType) -> None:
        if not hasattr(instance, "deleted_at"):
            raise TypeError(f"{type(instance).__name__} não suporta soft delete (sem SoftDeleteMixin).")
        instance.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.flush()
