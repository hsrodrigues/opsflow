"""Location repository.

Locations are not managed through their own screen yet (seção 12 describes
Rotas with plain "Origem"/"Destino" fields, not a separate cadastro) — the
route service resolves a location by name, creating one on the fly the
first time a name is used. This keeps `Route` correctly modeled against
`Location` (ready for the seção 22 map integration) without requiring a
standalone Location CRUD before Rotas can work.
"""
from sqlalchemy.orm import Session

from app.models.location import Location
from app.repositories.base import TenantRepository


class LocationRepository(TenantRepository[Location]):
    model = Location

    def get_by_name(self, name: str) -> Location | None:
        return self.db.execute(self._base_query().where(Location.name == name)).scalar_one_or_none()

    def get_or_create(self, name: str) -> Location:
        existing = self.get_by_name(name)
        if existing is not None:
            return existing
        location = Location(tenant_id=self.tenant_id, name=name)
        return self.add(location)


def get_or_create_location(db: Session, tenant_id: int, name: str) -> Location:
    return LocationRepository(db, tenant_id).get_or_create(name.strip())
