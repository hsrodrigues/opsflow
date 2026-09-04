"""Response schemas for `/api/v1/notifications` (seção 20)."""
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import NotificationSeverity


class NotificationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    message: str
    severity: NotificationSeverity
    related_entity_type: str | None
    related_entity_id: int | None
    read_at: datetime | None
    created_at: datetime
