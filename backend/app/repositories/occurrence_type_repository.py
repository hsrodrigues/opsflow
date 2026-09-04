"""OccurrenceType repository.

Same find-or-create pattern as `location_repository.py`: seção 14 lists
suggested type names (atraso, quebra, acidente, ...) but the model is
explicitly "tenant-configurable", so there's no separate cadastro screen —
`OccurrenceService` resolves a type by name, creating it the first time.
"""
from sqlalchemy.orm import Session

from app.models.occurrence_type import OccurrenceType
from app.repositories.base import TenantRepository


class OccurrenceTypeRepository(TenantRepository[OccurrenceType]):
    model = OccurrenceType

    def get_by_name(self, name: str) -> OccurrenceType | None:
        return self.db.execute(self._base_query().where(OccurrenceType.name == name)).scalar_one_or_none()

    def get_or_create(self, name: str) -> OccurrenceType:
        existing = self.get_by_name(name)
        if existing is not None:
            return existing
        occurrence_type = OccurrenceType(tenant_id=self.tenant_id, name=name)
        return self.add(occurrence_type)


def get_or_create_occurrence_type(db: Session, tenant_id: int, name: str) -> OccurrenceType:
    return OccurrenceTypeRepository(db, tenant_id).get_or_create(name.strip())
