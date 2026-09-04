"""ORM model registry.

Every model must be imported here so that `Base.metadata` is fully populated
before Alembic (or `Base.metadata.create_all`, used only by tests) inspects
it. Import this package — not individual modules — from anywhere that needs
the full metadata (`database/migrations/env.py`, test fixtures).
"""
from app.models.api_key import ApiKey
from app.models.attachment import Attachment
from app.models.audit_log import AuditLog
from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.carrier import Carrier
from app.models.driver import Driver
from app.models.integration_config import IntegrationConfig
from app.models.license import License
from app.models.location import Location
from app.models.notification import Notification
from app.models.occurrence import Occurrence
from app.models.occurrence_type import OccurrenceType
from app.models.operation import Operation
from app.models.plan import Plan
from app.models.role import Permission, Role, role_permissions
from app.models.route import Route
from app.models.schedule import Schedule, ScheduleItem
from app.models.session import PasswordResetToken, RefreshToken
from app.models.status_history import StatusHistory
from app.models.subscription import Subscription
from app.models.system_setting import SystemSetting
from app.models.tenant import Tenant
from app.models.user import User, user_roles
from app.models.vehicle import Vehicle
from app.models.vehicle_type import VehicleType

__all__ = [
    "ApiKey",
    "Attachment",
    "AuditLog",
    "AuditMixin",
    "Base",
    "Carrier",
    "Driver",
    "IntegrationConfig",
    "License",
    "Location",
    "Notification",
    "Occurrence",
    "OccurrenceType",
    "Operation",
    "PasswordResetToken",
    "Permission",
    "Plan",
    "RefreshToken",
    "Role",
    "Route",
    "Schedule",
    "ScheduleItem",
    "SoftDeleteMixin",
    "StatusHistory",
    "Subscription",
    "SystemSetting",
    "Tenant",
    "TenantMixin",
    "TimestampMixin",
    "User",
    "Vehicle",
    "VehicleType",
    "role_permissions",
    "user_roles",
]
