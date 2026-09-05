"""Wires the background jobs into APScheduler.

Started/stopped from `app.main`'s FastAPI startup/shutdown events — never
imported at module load time by anything else, so importing `app.jobs.*`
(e.g. from tests) never has the side effect of starting a real scheduler.
`JOBS_ENABLED=false` (set by `tests/backend/conftest.py`) keeps it off
during the test suite, where a background thread hitting the test database
on its own timer would make tests flaky.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.jobs import backup_job, cnh_alerts, delay_detection, license_expiration, stale_operations_job

logger = logging.getLogger("opsflow.jobs.scheduler")

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.jobs_enabled:
        logger.info("Jobs em background desabilitados (JOBS_ENABLED=false).")
        return
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        delay_detection.run, "interval", minutes=settings.delay_detection_interval_minutes,
        id="delay_detection", replace_existing=True,
    )
    _scheduler.add_job(
        cnh_alerts.run, "interval", hours=settings.cnh_alert_interval_hours,
        id="cnh_alerts", replace_existing=True,
    )
    _scheduler.add_job(
        license_expiration.run, "interval", minutes=settings.license_expiration_interval_minutes,
        id="license_expiration", replace_existing=True,
    )
    _scheduler.add_job(
        backup_job.run, "interval", hours=settings.backup_interval_hours,
        id="backup_job", replace_existing=True,
    )
    _scheduler.add_job(
        stale_operations_job.run, "interval", minutes=settings.stale_operations_interval_minutes,
        id="stale_operations_job", replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler de jobs iniciado (%d jobs registrados).", len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler de jobs finalizado.")
