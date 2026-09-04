"""`/api/v1/notifications` (seção 20)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.notification import NotificationOut
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    params: PageParams = Depends(),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("notifications.view")),
    db: Session = Depends(get_db),
) -> Page[NotificationOut]:
    items, total = notification_service.list_notifications(
        db, tenant_id, user.id, unread_only=unread_only, limit=params.page_size, offset=params.offset,
    )
    return Page.build([NotificationOut.model_validate(item) for item in items], total=total, params=params)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int, tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("notifications.view")), db: Session = Depends(get_db),
) -> NotificationOut:
    notification = notification_service.mark_as_read(db, tenant_id, user.id, notification_id)
    return NotificationOut.model_validate(notification)


@router.post("/read-all", response_model=dict)
def mark_all_notifications_read(
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_permission("notifications.view")), db: Session = Depends(get_db),
) -> dict:
    count = notification_service.mark_all_as_read(db, tenant_id, user.id)
    return {"marked": count}
