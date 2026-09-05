"""Robô 5: fechamento automático de pendências (seção 41 "Automações",
pedido explícito do cliente).

Operações penduradas há tempo demais num status intermediário
(AGUARDANDO/EM_FILA/EM_OPERACAO) sem ninguém ter mexido — alguém esqueceu de
marcar como concluída, por exemplo — nunca se resolvem sozinhas. Este robô
varre todos os tenants e fecha (CANCELADO) qualquer uma parada há mais de
`STALE_OPERATION_HOURS`, com uma nota explicando o motivo na timeline.
"""
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.jobs.recipients import recipients_for_tenant
from app.models.enums import NotificationSeverity
from app.models.tenant import Tenant
from app.services import notification_service, operation_service

logger = logging.getLogger("opsflow.jobs.stale_operations")


def run() -> None:
    db = SessionLocal()
    try:
        stale_after_hours = get_settings().stale_operation_hours
        tenant_ids = [row[0] for row in db.execute(select(Tenant.id).where(Tenant.is_active.is_(True))).all()]
        for tenant_id in tenant_ids:
            _sweep_tenant(db, tenant_id, stale_after_hours)
    except Exception:  # noqa: BLE001 - um robô em background nunca pode derrubar o processo
        logger.exception("Falha ao rodar fechamento automático de pendências")
    finally:
        db.close()


def _sweep_tenant(db, tenant_id: int, stale_after_hours: int) -> None:
    closed_item_ids = operation_service.close_stale_operations(db, tenant_id, stale_after_hours)
    if not closed_item_ids:
        return

    recipients = recipients_for_tenant(db, tenant_id)
    for item_id in closed_item_ids:
        for recipient in recipients:
            notification_service.create_notification(
                db, tenant_id=tenant_id, user_id=recipient.id, title="Operação fechada automaticamente",
                message=f"Uma operação ficou parada por mais de {stale_after_hours}h e foi fechada pelo sistema.",
                severity=NotificationSeverity.WARNING, related_entity_type="schedule_item",
                related_entity_id=item_id,
            )
    db.commit()
    logger.info(
        "%d operação(ões) fechada(s) automaticamente (tenant_id=%s)", len(closed_item_ids), tenant_id,
    )
