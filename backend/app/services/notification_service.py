"""Notification service (seção 20)."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import NotificationSeverity
from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository


def list_notifications(
    db: Session, tenant_id: int, user_id: int, *, unread_only: bool, limit: int, offset: int,
) -> tuple[list[Notification], int]:
    return NotificationRepository(db, tenant_id).list_for_user(
        user_id, unread_only=unread_only, limit=limit, offset=offset,
    )


def mark_as_read(db: Session, tenant_id: int, user_id: int, notification_id: int) -> Notification:
    repo = NotificationRepository(db, tenant_id)
    notification = repo.get_for_user(user_id, notification_id)
    if notification is None:
        raise NotFoundError("Notificação não encontrada.")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_as_read(db: Session, tenant_id: int, user_id: int) -> int:
    count = NotificationRepository(db, tenant_id).mark_all_read(user_id)
    db.commit()
    return count


def create_notification(
    db: Session, *, tenant_id: int, user_id: int | None, title: str, message: str,
    severity: NotificationSeverity = NotificationSeverity.INFO, related_entity_type: str | None = None,
    related_entity_id: int | None = None,
) -> Notification:
    """Low-level helper both the API (future manual notifications) and the
    background jobs (`app/jobs/`) use to create a notification the same way.
    Does not commit — callers own their own transaction boundary.
    """
    notification = Notification(
        tenant_id=tenant_id, user_id=user_id, title=title, message=message, severity=severity,
        related_entity_type=related_entity_type, related_entity_id=related_entity_id,
    )
    db.add(notification)
    db.flush()
    return notification
