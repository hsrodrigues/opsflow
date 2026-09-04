"""Route service — business rules for rotas (seção 12)."""
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import AuditAction
from app.models.route import Route
from app.models.user import User
from app.repositories.location_repository import get_or_create_location
from app.repositories.route_repository import RouteRepository
from app.schemas.route import RouteCreate, RouteOut, RouteUpdate
from app.services.audit_service import write_audit_log


def route_to_out(route: Route) -> RouteOut:
    return RouteOut(
        id=route.id, name=route.name, origin_name=route.origin.name, destination_name=route.destination.name,
        distance_km=route.distance_km, estimated_time_minutes=route.estimated_time_minutes,
        operation_type=route.operation_type, status=route.status,
    )


def _as_dict(route: Route) -> dict:
    return {
        "name": route.name, "origin": route.origin.name, "destination": route.destination.name,
        "status": route.status.value if hasattr(route.status, "value") else route.status,
    }


def list_routes(
    db: Session, tenant_id: int, *, query: str | None, status: str | None, limit: int, offset: int,
) -> tuple[list[Route], int]:
    return RouteRepository(db, tenant_id).search(query=query, status=status, limit=limit, offset=offset)


def get_route(db: Session, tenant_id: int, route_id: int) -> Route:
    route = RouteRepository(db, tenant_id).get(route_id)
    if route is None:
        raise NotFoundError("Rota não encontrada.")
    return route


def create_route(db: Session, tenant_id: int, actor: User, payload: RouteCreate, ip_address: str | None) -> Route:
    repo = RouteRepository(db, tenant_id)
    origin = get_or_create_location(db, tenant_id, payload.origin_name)
    destination = get_or_create_location(db, tenant_id, payload.destination_name)

    route = Route(
        tenant_id=tenant_id, name=payload.name, origin_location_id=origin.id, destination_location_id=destination.id,
        distance_km=payload.distance_km, estimated_time_minutes=payload.estimated_time_minutes,
        operation_type=payload.operation_type, created_by=actor.id, updated_by=actor.id,
    )
    repo.add(route)
    db.flush()
    route.origin, route.destination = origin, destination  # evita round-trip: já temos os objetos em mãos

    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.CREATE, table_name="routes",
        record_id=str(route.id), ip_address=ip_address, new_value=_as_dict(route),
    )
    db.commit()
    db.refresh(route)
    return route


def update_route(
    db: Session, tenant_id: int, actor: User, route_id: int, payload: RouteUpdate, ip_address: str | None,
) -> Route:
    route = get_route(db, tenant_id, route_id)
    old_value = _as_dict(route)

    fields = payload.model_dump(exclude_unset=True, exclude={"origin_name", "destination_name"})
    for field, value in fields.items():
        setattr(route, field, value)
    if payload.origin_name is not None:
        route.origin = get_or_create_location(db, tenant_id, payload.origin_name)
        route.origin_location_id = route.origin.id
    if payload.destination_name is not None:
        route.destination = get_or_create_location(db, tenant_id, payload.destination_name)
        route.destination_location_id = route.destination.id
    route.updated_by = actor.id
    db.flush()

    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.UPDATE, table_name="routes",
        record_id=str(route.id), ip_address=ip_address, old_value=old_value, new_value=_as_dict(route),
    )
    db.commit()
    db.refresh(route)
    return route


def delete_route(db: Session, tenant_id: int, actor: User, route_id: int, ip_address: str | None) -> None:
    repo = RouteRepository(db, tenant_id)
    route = get_route(db, tenant_id, route_id)
    old_value = _as_dict(route)
    repo.soft_delete(route)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.DELETE, table_name="routes",
        record_id=str(route_id), ip_address=ip_address, old_value=old_value,
    )
    db.commit()
