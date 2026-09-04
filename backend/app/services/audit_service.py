"""Audit trail service (seção 19) — the single place that writes both the
queryable `audit_logs` table and the append-only `logs/audit.log` file, so
every caller (auth, cadastros, future modules) produces the exact same
audit record shape instead of each service reinventing it slightly
differently.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging_config import get_audit_logger
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def write_audit_log(
    db: Session, *, tenant_id: int | None, user_id: int | None, action: AuditAction,
    table_name: str | None = None, record_id: str | None = None, ip_address: str | None = None,
    old_value: dict[str, Any] | None = None, new_value: dict[str, Any] | None = None,
) -> None:
    """Record one audit event. Does not commit — callers commit as part of their own transaction."""
    db.add(
        AuditLog(
            tenant_id=tenant_id, user_id=user_id, action=action, table_name=table_name, record_id=record_id,
            ip_address=ip_address, old_value=old_value, new_value=new_value, created_at=_utc_now(),
        )
    )
    get_audit_logger().info(
        "action=%s table=%s record_id=%s user_id=%s tenant_id=%s ip=%s",
        action.value, table_name, record_id, user_id, tenant_id, ip_address,
    )
