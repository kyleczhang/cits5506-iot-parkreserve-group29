"""Smoke-test that scheduler factories return a started BackgroundScheduler."""

from __future__ import annotations

from app.jobs.purge_evidence_images import start_purge_job
from app.jobs.reconcile_reservations import start_reconcile_job


def test_reconcile_scheduler_starts(app):
    sched = start_reconcile_job(app)
    try:
        assert sched.running
        assert sched.get_job("reconcile_reservations") is not None
    finally:
        sched.shutdown(wait=False)


def test_purge_scheduler_starts(app):
    sched = start_purge_job(app)
    try:
        assert sched.running
        assert sched.get_job("purge_evidence_images") is not None
    finally:
        sched.shutdown(wait=False)
