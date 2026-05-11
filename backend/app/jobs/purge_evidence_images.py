"""Nightly purge of conflict-evidence JPEGs older than 30 days.

Strong-evidence images are retained for 30 days, then deleted; the conflict
row itself is preserved for the audit trail.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from app.config import Settings

logger = logging.getLogger(__name__)


def start_purge_job(app: Flask) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    settings: Settings = app.config["APP_SETTINGS"]

    def _run() -> None:
        from app.services.conflict_service import purge_expired_evidence

        with app.app_context():
            try:
                purged = purge_expired_evidence()
                if purged:
                    logger.info("purge.run purged=%d", len(purged))
            except Exception:
                logger.exception("purge.error")

    scheduler.add_job(
        _run,
        "interval",
        hours=settings.purge_interval_hours,
        id="purge_evidence_images",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
