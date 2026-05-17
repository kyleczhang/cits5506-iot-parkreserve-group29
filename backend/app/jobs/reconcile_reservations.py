"""Backend-driven reservation sweeper.

Runs every 30 s. The backend owns the `no_show` and `conflict_weak`
timeout decisions outright — neither event is sourced from the Pi:

  * ACTIVE past arrival + grace → synthesise `no_show` (regardless of the
    current Pi-reported bay state, except when the bay is in CONFLICT —
    that means a strong conflict is open and the reservation is being
    deliberately preserved).
  * PENDING_CHECK_IN past check-in grace → synthesise `conflict_weak`.

The sweeper *never* synthesises `conflict_strong` — it has no LPR evidence,
so the strong-evidence path is reserved exclusively for real Pi events
(which the Pi will replay after reconnect via `cloud/system/resync`).

For idempotency, the sweeper generates a deterministic `source_event_id =
uuid5(reservation_id, kind, "safety_net")` so (a) repeated sweeper runs
collapse to a single breach, (b) if a real Pi event arrives later with its
own UUID, *both* writes succeed (different `source_event_id`s) but the
business state has already been set; the duplicate breach is harmless
because both UUIDs deterministically refer to the same reservation event,
*so* we ALSO check the reservation's status before re-firing.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from sqlalchemy import select

from app.config import Settings
from app.extensions import db
from app.models import (
    BayState,
    ParkingBay,
    Reservation,
    ReservationStatus,
)
from app.mqtt.topics import InternalEventPayload
from app.services.event_dispatcher import dispatch_event
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def _safety_net_event_id(reservation_id, kind: str):
    return uuid5(NAMESPACE_URL, f"reservation/{reservation_id}/{kind}/safety_net")


def run_once() -> dict[str, int]:
    settings: Settings = _settings()
    now = utcnow()

    no_show_cutoff = now - timedelta(minutes=settings.arrival_grace_minutes)
    no_show_rows = list(
        db.session.execute(
            select(Reservation, ParkingBay)
            .join(ParkingBay, Reservation.bay_id == ParkingBay.id)
            .where(
                Reservation.status == ReservationStatus.ACTIVE,
                Reservation.expected_arrival_time < no_show_cutoff,
                ParkingBay.state != BayState.CONFLICT,
            )
            .with_for_update(of=Reservation, skip_locked=True)
            .limit(100)
        )
    )
    for reservation, bay in no_show_rows:
        payload = InternalEventPayload(
            event="no_show",
            ts=now,
            event_id=_safety_net_event_id(reservation.id, "no_show"),
            reservation_id=reservation.id,
        )
        dispatch_event(bay_code=bay.code, payload=payload)

    weak_rows = list(
        db.session.execute(
            select(Reservation, ParkingBay)
            .join(ParkingBay, Reservation.bay_id == ParkingBay.id)
            .where(
                Reservation.status == ReservationStatus.PENDING_CHECK_IN,
                Reservation.check_in_grace_expires_at < now,
            )
            .with_for_update(of=Reservation, skip_locked=True)
            .limit(100)
        )
    )
    for reservation, bay in weak_rows:
        payload = InternalEventPayload(
            event="conflict_weak",
            ts=now,
            event_id=_safety_net_event_id(reservation.id, "conflict_weak"),
            reservation_id=reservation.id,
        )
        dispatch_event(bay_code=bay.code, payload=payload)

    return {"no_show": len(no_show_rows), "conflict_weak": len(weak_rows)}


def _settings() -> Settings:
    from flask import current_app

    return current_app.config["APP_SETTINGS"]


def start_reconcile_job(app: Flask) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    settings: Settings = app.config["APP_SETTINGS"]

    def _run() -> None:
        with app.app_context():
            try:
                result = run_once()
                if any(result.values()):
                    logger.info("reconcile.run %s", result)
            except Exception:
                logger.exception("reconcile.error")

    scheduler.add_job(
        _run,
        "interval",
        seconds=settings.reconcile_interval_seconds,
        id="reconcile_reservations",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
