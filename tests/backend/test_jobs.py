"""Tests for the background jobs (`app/jobs/`) — called directly via
`run()`, never through APScheduler (see `conftest.py`'s `JOBS_ENABLED=false`).
"""
from datetime import date, datetime, timedelta, timezone

from app.jobs import cnh_alerts, delay_detection, license_expiration, stale_operations_job
from app.models.carrier import Carrier
from app.models.driver import Driver
from app.models.enums import LicenseStatus, ScheduleStatus
from app.models.license import License
from app.models.notification import Notification
from app.models.operation import Operation
from app.models.schedule import Schedule, ScheduleItem
from app.services import operation_service, schedule_service
from tests.backend.factories import make_license, make_route, make_tenant, make_user


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_delay_detection_marks_overdue_items_and_notifies(db_session):
    tenant = make_tenant(db_session)
    admin = make_user(db_session, tenant, email="admin@delay-job.com")
    route = make_route(db_session, tenant)
    db_session.commit()

    schedule = Schedule(tenant_id=tenant.id, schedule_date=date.today(), shift="MANHA")
    db_session.add(schedule)
    db_session.flush()
    overdue_item = ScheduleItem(
        tenant_id=tenant.id, schedule_id=schedule.id, route_id=route.id,
        scheduled_at=_utc_now() - timedelta(hours=3), status=ScheduleStatus.PROGRAMADO,
    )
    db_session.add(overdue_item)
    db_session.commit()

    delay_detection.run()

    db_session.refresh(overdue_item)
    assert overdue_item.status == ScheduleStatus.ATRASADO

    notifications = db_session.query(Notification).filter(Notification.tenant_id == tenant.id).all()
    assert len(notifications) == 1
    assert notifications[0].user_id == admin.id
    assert "atrasada" in notifications[0].message


def test_delay_detection_leaves_on_time_items_alone(db_session):
    tenant = make_tenant(db_session)
    route = make_route(db_session, tenant)
    db_session.commit()

    schedule = Schedule(tenant_id=tenant.id, schedule_date=date.today(), shift="MANHA")
    db_session.add(schedule)
    db_session.flush()
    future_item = ScheduleItem(
        tenant_id=tenant.id, schedule_id=schedule.id, route_id=route.id,
        scheduled_at=_utc_now() + timedelta(hours=3), status=ScheduleStatus.PROGRAMADO,
    )
    db_session.add(future_item)
    db_session.commit()

    delay_detection.run()

    db_session.refresh(future_item)
    assert future_item.status == ScheduleStatus.PROGRAMADO


def test_cnh_alerts_notifies_once_per_dedup_window(db_session):
    tenant = make_tenant(db_session)
    admin = make_user(db_session, tenant, email="admin@cnh-job.com")
    carrier = Carrier(tenant_id=tenant.id, legal_name="Transportadora Teste")
    db_session.add(carrier)
    db_session.flush()
    driver = Driver(
        tenant_id=tenant.id, full_name="Motorista CNH Vencendo", cpf="111.111.111-11",
        cnh_expiry=date.today() + timedelta(days=10),
    )
    db_session.add(driver)
    db_session.commit()

    cnh_alerts.run()
    notifications = db_session.query(Notification).filter(Notification.tenant_id == tenant.id).all()
    assert len(notifications) == 1
    assert notifications[0].user_id == admin.id
    assert "10 dia" in notifications[0].message

    cnh_alerts.run()  # segunda execução não deve duplicar (dedup de 24h)
    notifications_after = db_session.query(Notification).filter(Notification.tenant_id == tenant.id).all()
    assert len(notifications_after) == 1


def test_license_expiration_transitions_status_and_notifies(db_session):
    tenant = make_tenant(db_session)
    admin = make_user(db_session, tenant, email="admin@license-job.com")
    make_license(db_session, tenant, status=LicenseStatus.ACTIVE)
    db_session.commit()

    license_ = db_session.query(License).filter(License.tenant_id == tenant.id).one()
    license_.expires_at = _utc_now() - timedelta(days=1)
    db_session.commit()

    license_expiration.run()

    db_session.refresh(license_)
    assert license_.status == LicenseStatus.EXPIRED

    notifications = db_session.query(Notification).filter(Notification.tenant_id == tenant.id).all()
    assert len(notifications) == 1
    assert notifications[0].user_id == admin.id
    assert notifications[0].severity.value == "CRITICAL"


def _make_stale_operation(db_session, tenant, route, *, status=ScheduleStatus.EM_OPERACAO, hours_stale=48):
    """Cria um `ScheduleItem` já numa `Operation` (via `change_status`, o
    mesmo caminho real de qualquer troca de status) e força o relógio pra
    trás — sem isso, `updated_at` seria "agora" e nunca pareceria parado."""
    schedule = Schedule(tenant_id=tenant.id, schedule_date=date.today(), shift="MANHA")
    db_session.add(schedule)
    db_session.flush()
    item = ScheduleItem(
        tenant_id=tenant.id, schedule_id=schedule.id, route_id=route.id,
        scheduled_at=_utc_now() - timedelta(hours=hours_stale + 1), status=ScheduleStatus.PROGRAMADO,
    )
    db_session.add(item)
    db_session.commit()

    schedule_service.change_status(db_session, tenant.id, None, item.id, status, None, ip_address=None)

    operation = db_session.query(Operation).filter(Operation.schedule_item_id == item.id).one()
    operation.updated_at = _utc_now() - timedelta(hours=hours_stale)
    db_session.commit()
    return item, operation


def test_close_stale_operations_cancels_items_stuck_past_the_cutoff(db_session):
    tenant = make_tenant(db_session)
    admin = make_user(db_session, tenant, email="admin@stale-job.com")
    route = make_route(db_session, tenant)
    db_session.commit()
    item, _operation = _make_stale_operation(db_session, tenant, route, hours_stale=30)

    closed_ids = operation_service.close_stale_operations(db_session, tenant.id, stale_after_hours=24)

    assert closed_ids == [item.id]
    db_session.refresh(item)
    assert item.status == ScheduleStatus.CANCELADO
    operation = db_session.query(Operation).filter(Operation.schedule_item_id == item.id).one()
    assert operation.status == ScheduleStatus.CANCELADO

    history = schedule_service.get_status_history(db_session, tenant.id, item.id)
    assert history[-1].new_status == ScheduleStatus.CANCELADO
    assert "fechado automaticamente" in (history[-1].notes or "").lower()
    assert admin.id  # documenta que existe um recipiente pro robô notificar (ver o teste dedicado abaixo)


def test_close_stale_operations_leaves_recent_ones_alone(db_session):
    tenant = make_tenant(db_session)
    route = make_route(db_session, tenant)
    db_session.commit()
    item, _operation = _make_stale_operation(db_session, tenant, route, hours_stale=2)

    closed_ids = operation_service.close_stale_operations(db_session, tenant.id, stale_after_hours=24)

    assert closed_ids == []
    db_session.refresh(item)
    assert item.status == ScheduleStatus.EM_OPERACAO


def test_stale_operations_job_notifies_recipients(db_session):
    tenant = make_tenant(db_session)
    admin = make_user(db_session, tenant, email="admin@stale-job-run.com")
    route = make_route(db_session, tenant)
    db_session.commit()
    _make_stale_operation(db_session, tenant, route, hours_stale=48)

    stale_operations_job._sweep_tenant(db_session, tenant.id, stale_after_hours=24)

    notifications = db_session.query(Notification).filter(Notification.tenant_id == tenant.id).all()
    assert len(notifications) == 1
    assert notifications[0].user_id == admin.id
    assert "fechada automaticamente" in notifications[0].title.lower()
