"""Robô 3: expiração automática de licença (seção 6).

Today a license's status only reflects reality when a login happens to
re-check it — this job transitions `ACTIVE`/`TRIAL` licenses past their
`expires_at` into `EXPIRED` on its own, and notifies the tenant's admins
instead of leaving that discovery to whoever logs in next.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.jobs.recipients import recipients_for_tenant
from app.models.enums import LicenseStatus, NotificationSeverity
from app.models.license import License
from app.repositories.notification_repository import NotificationRepository
from app.services import notification_service

logger = logging.getLogger("opsflow.jobs.license_expiration")

_DEDUP_HOURS = 24
_ACTIVE_LICENSE_STATUSES = (LicenseStatus.ACTIVE, LicenseStatus.TRIAL)


def run() -> None:
    db = SessionLocal()
    try:
        _sweep(db)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao rodar expiração automática de licenças")
    finally:
        db.close()


def _sweep(db: Session) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stmt = select(License).where(
        License.status.in_(_ACTIVE_LICENSE_STATUSES), License.expires_at.is_not(None), License.expires_at < now,
    )
    for license_ in list(db.execute(stmt).scalars().all()):
        license_.status = LicenseStatus.EXPIRED
        db.flush()

        notification_repo = NotificationRepository(db, license_.tenant_id)
        already_notified = notification_repo.recently_notified(
            related_entity_type="license", related_entity_id=license_.id, within_hours=_DEDUP_HOURS,
        )
        if not already_notified:
            for recipient in recipients_for_tenant(db, license_.tenant_id):
                notification_service.create_notification(
                    db, tenant_id=license_.tenant_id, user_id=recipient.id, title="Licença expirada",
                    message="A licença da sua empresa expirou. Contate o suporte para renovar.",
                    severity=NotificationSeverity.CRITICAL, related_entity_type="license",
                    related_entity_id=license_.id,
                )
        db.commit()
        logger.info("License %s expirada automaticamente (tenant_id=%s)", license_.id, license_.tenant_id)
