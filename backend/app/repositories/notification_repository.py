"""Notification repository (seção 20).

A notification with `user_id=None` is a tenant-wide broadcast — everyone in
the tenant sees it — so every read here matches `user_id == user_id OR
user_id IS NULL`. Note that this means a broadcast row's `read_at` is
shared: whoever marks it read, marks it read for the whole tenant. That's an
accepted simplification for the MVP (a proper per-viewer read state would
need a separate join table); every notification the background jobs create
(see `app/jobs/`) is addressed to a specific user for exactly this reason,
so it never hits that edge case in practice.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from app.models.notification import Notification
from app.repositories.base import TenantRepository


class NotificationRepository(TenantRepository[Notification]):
    model = Notification

    def _for_user_query(self, user_id: int):
        return self._base_query().where(or_(Notification.user_id == user_id, Notification.user_id.is_(None)))

    def list_for_user(
        self, user_id: int, *, unread_only: bool = False, limit: int = 20, offset: int = 0,
    ) -> tuple[list[Notification], int]:
        stmt = self._for_user_query(user_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items_stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        items = list(self.db.execute(items_stmt).scalars().all())
        return items, total

    def get_for_user(self, user_id: int, notification_id: int) -> Notification | None:
        stmt = self._for_user_query(user_id).where(Notification.id == notification_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def mark_all_read(self, user_id: int) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = self._for_user_query(user_id).where(Notification.read_at.is_(None))
        unread = list(self.db.execute(stmt).scalars().all())
        for notification in unread:
            notification.read_at = now
        self.db.flush()
        return len(unread)

    def recently_notified(
        self, *, related_entity_type: str, related_entity_id: int, within_hours: int = 24,
    ) -> bool:
        """Whether a notification for this entity was already created recently — the
        dedup check the background jobs (seção 20) use so a recurring sweep
        doesn't resend the same alert every run.
        """
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=within_hours)
        stmt = select(func.count()).select_from(Notification).where(
            Notification.tenant_id == self.tenant_id,
            Notification.related_entity_type == related_entity_type,
            Notification.related_entity_id == related_entity_id,
            Notification.created_at >= cutoff,
        )
        return self.db.execute(stmt).scalar_one() > 0
