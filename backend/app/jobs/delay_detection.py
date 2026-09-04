"""Robô 1: detecção automática de atraso (seção 21).

Sweeps every tenant looking for schedule items still in an active status
whose expected arrival time has passed, and moves them to `ATRASADO`
automatically — today this only happens if a human notices and clicks
through the "Status" dialog. Runs on its own DB session (background
threads never share the request-scoped session from `get_db`).
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.jobs.recipients import recipients_for_tenant
from app.models.enums import NotificationSeverity, ScheduleStatus
from app.models.route import Route
from app.models.schedule import ScheduleItem
from app.models.tenant import Tenant
from app.services import notification_service, schedule_service

logger = logging.getLogger("opsflow.jobs.delay_detection")

_DEFAULT_TOLERANCE_MINUTES = 60  # usado quando a rota não tem estimated_time_minutes
_ACTIVE_STATUSES = (
    ScheduleStatus.PROGRAMADO, ScheduleStatus.AGUARDANDO, ScheduleStatus.EM_FILA, ScheduleStatus.EM_OPERACAO,
)


def run() -> None:
    """Entry point registered with APScheduler — never raises, only logs."""
    db = SessionLocal()
    try:
        _sweep_all_tenants(db)
    except Exception:  # noqa: BLE001 - um job em background nunca pode derrubar o processo
        logger.exception("Falha ao rodar detecção automática de atraso")
    finally:
        db.close()


def _sweep_all_tenants(db: Session) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    tenant_ids = [row[0] for row in db.execute(select(Tenant.id).where(Tenant.is_active.is_(True))).all()]
    for tenant_id in tenant_ids:
        _sweep_tenant(db, tenant_id, now)


def _sweep_tenant(db: Session, tenant_id: int, now: datetime) -> None:
    stmt = (
        select(ScheduleItem)
        .join(Route, ScheduleItem.route_id == Route.id)
        .where(
            ScheduleItem.tenant_id == tenant_id, ScheduleItem.deleted_at.is_(None),
            ScheduleItem.status.in_(_ACTIVE_STATUSES),
        )
    )
    candidates = list(db.execute(stmt).scalars().all())
    overdue = [
        item for item in candidates
        if now >= item.scheduled_at + timedelta(minutes=item.route.estimated_time_minutes or _DEFAULT_TOLERANCE_MINUTES)
    ]
    if not overdue:
        return

    recipients = recipients_for_tenant(db, tenant_id)
    for item in overdue:
        updated = schedule_service.change_status(
            db, tenant_id, None, item.id, ScheduleStatus.ATRASADO,
            "Marcado automaticamente como atrasado pelo sistema.", ip_address=None,
        )
        for recipient in recipients:
            notification_service.create_notification(
                db, tenant_id=tenant_id, user_id=recipient.id, title="Operação atrasada",
                message=f"A operação da rota {updated.route.name} está atrasada.",
                severity=NotificationSeverity.WARNING, related_entity_type="schedule_item",
                related_entity_id=updated.id,
            )
        db.commit()
        logger.info("schedule_item %s marcado como ATRASADO (tenant_id=%s)", item.id, tenant_id)
