"""Tests for the archiving feature (seção 41 "Automações", pedido explícito
do cliente: "arquivamento de dados antigos... mantendo as tabelas
principais leves"). O suite roda contra SQLite, então exercita o fallback
Python/ORM de `archive_service.py` — a MESMA regra de negócio que a stored
procedure `sp_archive_old_records` aplica em MySQL (verificada à parte,
contra um MySQL de verdade)."""
from datetime import date, datetime, timedelta, timezone

from app.models.archive import OccurrenceArchive, OperationArchive, ScheduleItemArchive, StatusHistoryArchive
from app.models.attachment import Attachment
from app.models.enums import OccurrenceStatus, ScheduleStatus
from app.models.occurrence import Occurrence
from app.models.occurrence_type import OccurrenceType
from app.models.operation import Operation
from app.models.schedule import Schedule, ScheduleItem
from app.services import archive_service, schedule_service
from tests.backend.factories import make_route, make_tenant, make_user


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_operation(db_session, tenant, route, *, status, updated_at):
    schedule = Schedule(tenant_id=tenant.id, schedule_date=date.today(), shift="MANHA")
    db_session.add(schedule)
    db_session.flush()
    item = ScheduleItem(
        tenant_id=tenant.id, schedule_id=schedule.id, route_id=route.id, scheduled_at=_utc_now(),
        status=ScheduleStatus.PROGRAMADO,
    )
    db_session.add(item)
    db_session.commit()

    schedule_service.change_status(db_session, tenant.id, None, item.id, ScheduleStatus.EM_OPERACAO, None, None)
    if status != ScheduleStatus.EM_OPERACAO:
        schedule_service.change_status(db_session, tenant.id, None, item.id, status, None, None)

    operation = db_session.query(Operation).filter(Operation.schedule_item_id == item.id).one()
    operation.updated_at = updated_at
    db_session.commit()
    return item, operation


def _make_occurrence_type(db_session, tenant):
    occurrence_type = OccurrenceType(tenant_id=tenant.id, name="Atraso")
    db_session.add(occurrence_type)
    db_session.flush()
    return occurrence_type


def test_archives_old_finished_operations_and_deletes_from_live_tables(db_session):
    tenant = make_tenant(db_session)
    route = make_route(db_session, tenant)
    db_session.commit()
    old_cutoff = _utc_now() - timedelta(days=400)
    item, operation = _make_operation(
        db_session, tenant, route, status=ScheduleStatus.CONCLUIDO, updated_at=old_cutoff,
    )
    item_id, operation_id = item.id, operation.id

    result = archive_service.archive_old_records(db_session, tenant.id, older_than_months=12)

    assert result["operations_archived"] == 1
    assert db_session.get(Operation, operation_id) is None
    assert db_session.get(ScheduleItem, item_id) is None
    assert db_session.query(OperationArchive).filter(OperationArchive.id == operation_id).one() is not None
    assert db_session.query(ScheduleItemArchive).filter(ScheduleItemArchive.id == item_id).one() is not None
    assert db_session.query(StatusHistoryArchive).filter(StatusHistoryArchive.operation_id == operation_id).count() >= 1


def test_leaves_recent_finished_operations_in_the_live_tables(db_session):
    tenant = make_tenant(db_session)
    route = make_route(db_session, tenant)
    db_session.commit()
    item, operation = _make_operation(
        db_session, tenant, route, status=ScheduleStatus.CONCLUIDO, updated_at=_utc_now() - timedelta(days=5),
    )

    result = archive_service.archive_old_records(db_session, tenant.id, older_than_months=12)

    assert result["operations_archived"] == 0
    assert db_session.get(Operation, operation.id) is not None
    assert db_session.get(ScheduleItem, item.id) is not None


def test_leaves_old_but_still_active_operations_alone(db_session):
    """CONCLUIDO/CANCELADO só — uma operação ainda em andamento nunca é
    candidata a arquivamento, não importa a idade."""
    tenant = make_tenant(db_session)
    route = make_route(db_session, tenant)
    db_session.commit()
    item, operation = _make_operation(
        db_session, tenant, route, status=ScheduleStatus.EM_OPERACAO, updated_at=_utc_now() - timedelta(days=400),
    )

    result = archive_service.archive_old_records(db_session, tenant.id, older_than_months=12)

    assert result["operations_archived"] == 0
    assert db_session.get(Operation, operation.id) is not None


def test_skips_operations_still_linked_to_an_occurrence(db_session):
    tenant = make_tenant(db_session)
    route = make_route(db_session, tenant)
    db_session.commit()
    item, operation = _make_operation(
        db_session, tenant, route, status=ScheduleStatus.CONCLUIDO, updated_at=_utc_now() - timedelta(days=400),
    )
    occurrence_type = _make_occurrence_type(db_session, tenant)
    db_session.add(Occurrence(
        tenant_id=tenant.id, occurrence_type_id=occurrence_type.id, operation_id=operation.id,
        description="Atraso na entrega.", occurred_at=_utc_now(),
    ))
    db_session.commit()

    result = archive_service.archive_old_records(db_session, tenant.id, older_than_months=12)

    assert result["operations_archived"] == 0
    assert db_session.get(Operation, operation.id) is not None


def test_archives_old_resolved_occurrences_without_attachments(db_session):
    tenant = make_tenant(db_session)
    occurrence_type = _make_occurrence_type(db_session, tenant)
    db_session.commit()
    occurrence = Occurrence(
        tenant_id=tenant.id, occurrence_type_id=occurrence_type.id, description="Pneu furado.",
        status=OccurrenceStatus.RESOLVIDA, occurred_at=_utc_now(), created_at=_utc_now() - timedelta(days=400),
    )
    db_session.add(occurrence)
    db_session.commit()
    occurrence_id = occurrence.id

    result = archive_service.archive_old_records(db_session, tenant.id, older_than_months=12)

    assert result["occurrences_archived"] == 1
    assert db_session.get(Occurrence, occurrence_id) is None
    assert db_session.query(OccurrenceArchive).filter(OccurrenceArchive.id == occurrence_id).one() is not None


def test_skips_occurrences_that_have_attachments(db_session):
    tenant = make_tenant(db_session)
    occurrence_type = _make_occurrence_type(db_session, tenant)
    db_session.commit()
    occurrence = Occurrence(
        tenant_id=tenant.id, occurrence_type_id=occurrence_type.id, description="Colisão leve.",
        status=OccurrenceStatus.RESOLVIDA, occurred_at=_utc_now(), created_at=_utc_now() - timedelta(days=400),
    )
    db_session.add(occurrence)
    db_session.flush()
    db_session.add(Attachment(
        tenant_id=tenant.id, occurrence_id=occurrence.id, file_name="foto.jpg", file_path="/tmp/foto.jpg",
    ))
    db_session.commit()

    result = archive_service.archive_old_records(db_session, tenant.id, older_than_months=12)

    assert result["occurrences_archived"] == 0
    assert db_session.get(Occurrence, occurrence.id) is not None


def test_rejects_older_than_months_below_one(db_session):
    from app.core.exceptions import ValidationFailedError

    tenant = make_tenant(db_session)
    db_session.commit()
    try:
        archive_service.archive_old_records(db_session, tenant.id, older_than_months=0)
        assert False, "deveria ter levantado ValidationFailedError"
    except ValidationFailedError:
        pass


def _super_admin_headers(client, db_session, *, email: str = "plataforma@opsflow.local") -> dict:
    from app.core.security import hash_password
    from app.models.role import Role
    from app.models.user import User

    role = db_session.query(Role).filter(Role.code == "SUPER_ADMIN").one()
    user = User(tenant_id=None, email=email, full_name="Admin Plataforma", password_hash=hash_password("Sup3rSecret!"))
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_archive_endpoint_requires_platform_admin(client, db_session):
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="regular@archive-test.com")
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"email": "regular@archive-test.com", "password": "Sup3rSecret!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.post("/api/v1/platform/archive", json={"older_than_months": 12}).status_code == 401
    assert client.post(
        "/api/v1/platform/archive", headers=headers, json={"older_than_months": 12}
    ).status_code == 403


def test_archive_endpoint_sums_across_every_tenant(client, db_session):
    tenant_a = make_tenant(db_session, legal_name="Empresa A Ltda")
    tenant_b = make_tenant(db_session, legal_name="Empresa B Ltda")
    route_a = make_route(db_session, tenant_a)
    route_b = make_route(db_session, tenant_b)
    db_session.commit()
    _make_operation(db_session, tenant_a, route_a, status=ScheduleStatus.CONCLUIDO, updated_at=_utc_now() - timedelta(days=400))
    _make_operation(db_session, tenant_b, route_b, status=ScheduleStatus.CANCELADO, updated_at=_utc_now() - timedelta(days=400))
    headers = _super_admin_headers(client, db_session)

    response = client.post("/api/v1/platform/archive", headers=headers, json={"older_than_months": 12})

    assert response.status_code == 200
    assert response.json()["operations_archived"] == 2
