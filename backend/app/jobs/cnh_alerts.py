"""Robô 2: alerta de CNH próxima do vencimento (seção 10/20).

`DriverRepository.expiring_cnh` already finds the drivers; this job just
sweeps every tenant, notifies the right people, and remembers who it already
told (via `NotificationRepository.recently_notified`) so a driver whose CNH
still hasn't been renewed doesn't get re-notified every single run.
"""
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.jobs.recipients import recipients_for_tenant
from app.models.enums import NotificationSeverity
from app.models.tenant import Tenant
from app.repositories.driver_repository import DriverRepository
from app.repositories.notification_repository import NotificationRepository
from app.services import notification_service

logger = logging.getLogger("opsflow.jobs.cnh_alerts")

_WARNING_DAYS = 30
_DEDUP_HOURS = 24


def run() -> None:
    db = SessionLocal()
    try:
        tenant_ids = [row[0] for row in db.execute(select(Tenant.id).where(Tenant.is_active.is_(True))).all()]
        for tenant_id in tenant_ids:
            _check_tenant(db, tenant_id)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao rodar alerta de CNH vencendo")
    finally:
        db.close()


def _check_tenant(db: Session, tenant_id: int) -> None:
    drivers = DriverRepository(db, tenant_id).expiring_cnh(within_days=_WARNING_DAYS)
    if not drivers:
        return

    notification_repo = NotificationRepository(db, tenant_id)
    recipients = recipients_for_tenant(db, tenant_id)
    for driver in drivers:
        if notification_repo.recently_notified(
            related_entity_type="driver", related_entity_id=driver.id, within_hours=_DEDUP_HOURS,
        ):
            continue

        days_left = (driver.cnh_expiry - date.today()).days
        message = (
            f"A CNH do motorista {driver.full_name} já venceu."
            if days_left < 0 else f"A CNH do motorista {driver.full_name} vence em {days_left} dia(s)."
        )
        for recipient in recipients:
            notification_service.create_notification(
                db, tenant_id=tenant_id, user_id=recipient.id, title="CNH próxima do vencimento", message=message,
                severity=NotificationSeverity.WARNING, related_entity_type="driver", related_entity_id=driver.id,
            )
        db.commit()
        logger.info("Alerta de CNH enviado para driver_id=%s (tenant_id=%s)", driver.id, tenant_id)
