"""Structured, rotating logging setup.

Produces three rotating log files under `settings.log_dir`:
- application.log — general application activity (INFO+)
- errors.log       — errors and exceptions only (ERROR+)
- audit.log        — business-level audit trail (written explicitly by the
                      audit service, never automatically from log calls)

Passwords, tokens and other secrets must never be passed to these loggers —
callers are responsible for redacting sensitive fields before logging.
"""
import logging
import logging.handlers
from pathlib import Path

from app.core.config import get_settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging() -> None:
    """Configure root, error and audit loggers with rotating file handlers."""
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_LOG_FORMAT)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    app_handler = logging.handlers.RotatingFileHandler(
        log_dir / "application.log", maxBytes=10_485_760, backupCount=5, encoding="utf-8"
    )
    app_handler.setFormatter(formatter)
    root_logger.addHandler(app_handler)

    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "errors.log", maxBytes=10_485_760, backupCount=5, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # Dedicated audit logger: does not propagate to the root handlers above,
    # so audit entries only ever land in audit.log via explicit calls from
    # the audit service.
    audit_logger = logging.getLogger("opsflow.audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    audit_handler = logging.handlers.RotatingFileHandler(
        log_dir / "audit.log", maxBytes=10_485_760, backupCount=10, encoding="utf-8"
    )
    audit_handler.setFormatter(formatter)
    audit_logger.addHandler(audit_handler)


def get_audit_logger() -> logging.Logger:
    """Return the dedicated audit-trail logger."""
    return logging.getLogger("opsflow.audit")
