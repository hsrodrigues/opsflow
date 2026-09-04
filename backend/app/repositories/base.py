"""Base repository — the single enforcement point for tenant isolation.

Every repository for a tenant-scoped entity should extend `TenantRepository`
instead of querying `Session` directly. `tenant_id` is bound once, in
`__init__`, from the authenticated request (see `app/api/deps.py`) — never
passed per-call — so it is structurally impossible for a query built through
this class to "forget" the filter (seção 3/52/53).
"""
from typing import Generic, TypeVar

from sqlalchemy import select
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

    def _base_query(self):
        return select(self.model).where(self.model.tenant_id == self.tenant_id)

    def get(self, record_id: int) -> ModelType | None:
        return self.db.execute(self._base_query().where(self.model.id == record_id)).scalar_one_or_none()

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelType]:
        query = self._base_query().limit(limit).offset(offset)
        return list(self.db.execute(query).scalars().all())

    def add(self, instance: ModelType) -> ModelType:
        if getattr(instance, "tenant_id", None) != self.tenant_id:
            raise ValueError("Tentativa de persistir um registro com tenant_id diferente do repositório.")
        self.db.add(instance)
        self.db.flush()
        return instance
