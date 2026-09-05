"""Robô 4: backup automático do banco (seção 41 "Automações").

Diferente dos outros robôs desta pasta, não varre tenants — um backup é do
banco inteiro de uma vez (`mysqldump` não recorta por `tenant_id`), então
não abre `SessionLocal()` como os demais: chama `backup_service` direto, que
fala com o MySQL via subprocess, não via SQLAlchemy.
"""
import logging

from app.services import backup_service

logger = logging.getLogger("opsflow.jobs.backup")


def run() -> None:
    try:
        path = backup_service.create_backup()
        logger.info("Backup automático concluído: %s", path.name)
    except Exception:  # noqa: BLE001 - mesmo contrato dos outros robôs: nunca derruba o scheduler
        logger.exception("Falha ao rodar o backup automático")
