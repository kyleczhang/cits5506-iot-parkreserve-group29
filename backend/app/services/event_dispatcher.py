"""Pi → backend event dispatcher.

Each handler is idempotent on ``source_event_id``. Replays after backend
reconnect are no-ops, so penalty captures and refunds are never doubled.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from flask import current_app
from sqlalchemy import select

from app.config import Settings
from app.extensions import db
from app.models import (
    BayEventKind,
    BayState,
    CheckInMechanism,
    ParkingBay,
    PenaltyKind,
    Reservation,
    ReservationStatus,
)
from app.mqtt.topics import EventPayload
from app.services import (
    conflict_service,
    event_service,
    notification_service,
    payment_service,
    plate_service,
)
from app.services.mqtt_publisher import publish_reservation_command

logger = logging.getLogger(__name__)


def dispatch_event(*, bay_code: str, payload: EventPayload) -> None:
    bay = db.session.execute(
        select(ParkingBay).where(ParkingBay.code == bay_code)
    ).scalar_one_or_none()
    if bay is None:
        logger.warning("event.unknown_bay code=%s event=%s", bay_code, payload.event)
        return

    handler = _HANDLERS.get(payload.event)
    if handler is None:
        logger.warning("event.no_handler event=%s", payload.event)
        return
    handler(bay, payload)


# ---------------------------------------------------------------------------
# Handlers — bay context, payload-typed.
# ---------------------------------------------------------------------------


def _on_sensor_online(bay: ParkingBay, payload: EventPayload) -> None:
    if bay.state == BayState.OFFLINE:
        bay.state = BayState.AVAILABLE
    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.SENSOR_ONLINE,
        source_event_id=payload.event_id,
    )
    db.session.commit()
    notification_service.push_bay_updated(bay)


def _on_sensor_offline(bay: ParkingBay, payload: EventPayload) -> None:
    bay.state = BayState.OFFLINE
    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.SENSOR_OFFLINE,
        source_event_id=payload.event_id,
    )
    db.session.commit()
    notification_service.push_bay_updated(bay)


def _on_pending_check_in(bay: ParkingBay, payload: EventPayload) -> None:
    """Pi reports vehicle in reserved bay, LPR did not auto-resolve.

    Transition reservation → PENDING_CHECK_IN, set 5-min check-in grace,
    flip bay state, and notify the holder.
    """
    settings: Settings = current_app.config["APP_SETTINGS"]
    reservation = _open_reservation(bay)
    if reservation is None:
        logger.info("event.pending_no_reservation bay=%s", bay.code)
        return
    if reservation.status not in {
        ReservationStatus.ACTIVE,
        ReservationStatus.PENDING_CHECK_IN,
    }:
        return

    reservation.status = ReservationStatus.PENDING_CHECK_IN
    reservation.check_in_grace_expires_at = payload.ts + timedelta(
        minutes=settings.check_in_grace_minutes
    )
    if bay.state != BayState.PENDING_CHECK_IN:
        old_state = bay.state
        bay.state = BayState.PENDING_CHECK_IN
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.STATE_CHANGED,
            from_state=old_state,
            to_state=BayState.PENDING_CHECK_IN,
            reservation_id=reservation.id,
        )

    event = event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.PENDING_CHECK_IN,
        reservation_id=reservation.id,
        source_event_id=payload.event_id,
        payload={"detected_at": payload.ts.isoformat()},
    )
    if event is None and payload.event_id is not None:
        # replay
        db.session.rollback()
        return
    db.session.commit()

    notification_service.push_pending_check_in(
        user=reservation.user,
        bay=bay,
        reservation=reservation,
    )
    notification_service.push_bay_updated(bay)
    notification_service.push_reservation_updated(reservation, bay)


def _on_auto_check_in(bay: ParkingBay, payload: EventPayload) -> None:
    """Pi `auto_check_in` — LPR plate match, no user action required."""
    if not payload.recognised_plate:
        logger.warning("event.auto_check_in_missing_plate bay=%s", bay.code)
        return

    reservation = _open_reservation(bay)
    if reservation is None:
        logger.info("event.auto_check_in_no_reservation bay=%s", bay.code)
        return
    if reservation.status == ReservationStatus.CHECKED_IN:
        # idempotent
        return
    if reservation.status not in {
        ReservationStatus.ACTIVE,
        ReservationStatus.PENDING_CHECK_IN,
    }:
        return

    reservation.status = ReservationStatus.CHECKED_IN
    reservation.checked_in_at = payload.ts
    reservation.check_in_mechanism = CheckInMechanism.AUTO_LPR
    reservation.check_in_recognised_plate = payload.recognised_plate

    if bay.state != BayState.RESERVED_CHECKED_IN:
        old_state = bay.state
        bay.state = BayState.RESERVED_CHECKED_IN
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.STATE_CHANGED,
            from_state=old_state,
            to_state=BayState.RESERVED_CHECKED_IN,
            reservation_id=reservation.id,
        )

    event = event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.AUTO_CHECK_IN,
        reservation_id=reservation.id,
        source_event_id=payload.event_id,
        payload={
            "recognised_plate": payload.recognised_plate,
            "lpr_confidence": payload.lpr_confidence,
        },
    )
    if event is None and payload.event_id is not None:
        db.session.rollback()
        return
    db.session.commit()

    notification_service.push_auto_check_in(
        user=reservation.user,
        bay=bay,
        reservation=reservation,
        recognised_plate=payload.recognised_plate,
    )
    notification_service.push_bay_updated(bay)
    notification_service.push_reservation_updated(reservation, bay)


def _on_check_in_confirmed(bay: ParkingBay, payload: EventPayload) -> None:
    """Pi echoes a successful user-initiated QR / manual check-in."""
    reservation = _open_reservation(bay)
    if reservation is None:
        return
    if reservation.status == ReservationStatus.CHECKED_IN:
        # already set by REST handler — record audit only
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.CHECK_IN_CONFIRMED,
            reservation_id=reservation.id,
            source_event_id=payload.event_id,
        )
        db.session.commit()
        return
    # If we somehow got the echo first, set CHECKED_IN with mechanism=manual
    # (we don't know which fallback the user used; default to manual).
    if reservation.status in {
        ReservationStatus.ACTIVE,
        ReservationStatus.PENDING_CHECK_IN,
    }:
        reservation.status = ReservationStatus.CHECKED_IN
        reservation.checked_in_at = payload.ts
        reservation.check_in_mechanism = CheckInMechanism.MANUAL
        reservation.check_in_recognised_plate = None
        bay.state = BayState.RESERVED_CHECKED_IN
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.CHECK_IN_CONFIRMED,
            reservation_id=reservation.id,
            source_event_id=payload.event_id,
        )
        db.session.commit()
        notification_service.push_bay_updated(bay)
        notification_service.push_reservation_updated(reservation, bay)


def _on_conflict_strong(bay: ParkingBay, payload: EventPayload) -> None:
    """Strong-evidence conflict: LPR plate ∉ user's bound plates.

    Treated as a **facility-side occupancy incident**, not a reservation
    terminator: the holder's reservation is preserved while the wrong vehicle
    sits in the bay (status stays ``ACTIVE`` or ``CHECKED_IN``; a
    ``PENDING_CHECK_IN`` reservation rolls back to ``ACTIVE`` since the Pi has
    proven the present vehicle isn't theirs). No refund is issued here — that
    is owned by :func:`reservation_service.admin_terminate` and only fires
    when an admin explicitly terminates. If the wrong vehicle drives away,
    :mod:`app.services.bay_service` resolves the conflict as ``vehicle_left``
    and restores the reservation cache.

    The Pi separately uploads the JPEG to
    /api/v1/internal/conflicts/evidence keyed by ``source_event_id``.
    """
    if not payload.recognised_plate:
        logger.warning("event.conflict_strong_missing_plate bay=%s", bay.code)
        return
    if payload.event_id is None:
        logger.warning("event.conflict_strong_missing_event_id bay=%s", bay.code)
        return

    reservation = _open_reservation(bay)

    # Idempotency check: if we've already processed this event_id, do nothing.
    if event_service.already_processed(payload.event_id):
        return

    conflict = conflict_service.upsert_strong(
        bay=bay,
        reservation_id=reservation.id if reservation is not None else None,
        source_event_id=payload.event_id,
        recognised_plate=payload.recognised_plate,
        lpr_confidence=payload.lpr_confidence,
        detected_at=payload.ts,
    )

    # Reservation status under strong conflict:
    #   PENDING_CHECK_IN → ACTIVE (Pi proved the present car isn't the holder's;
    #                              the holder is once again "yet to arrive").
    #   ACTIVE           → unchanged.
    #   CHECKED_IN       → unchanged (the holder already checked in; this is a
    #                                 facility incident overlaid on a live
    #                                 session).
    # IN_CONFLICT is reserved for weak conflicts only.
    if reservation is not None and reservation.status == ReservationStatus.PENDING_CHECK_IN:
        reservation.status = ReservationStatus.ACTIVE
        reservation.check_in_grace_expires_at = None

    if bay.state != BayState.CONFLICT:
        old_state = bay.state
        bay.state = BayState.CONFLICT
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.STATE_CHANGED,
            from_state=old_state,
            to_state=BayState.CONFLICT,
            reservation_id=reservation.id if reservation else None,
        )

    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.CONFLICT_STRONG,
        reservation_id=reservation.id if reservation else None,
        source_event_id=payload.event_id,
        payload={
            "recognised_plate": payload.recognised_plate,
            "lpr_confidence": payload.lpr_confidence,
            "conflict_id": str(conflict.id),
        },
    )
    db.session.commit()

    notification_service.push_conflict_alert(conflict=conflict, bay=bay)
    notification_service.push_bay_updated(bay)
    if reservation is not None:
        notification_service.push_reservation_updated(reservation, bay)


def _on_conflict_weak(bay: ParkingBay, payload: EventPayload) -> None:
    """Weak-evidence conflict: LPR did not auto-resolve and grace expired.

    Captures a ``weak_conflict`` penalty against the reservation holder's
    deposit and releases the remainder.
    """
    if payload.event_id is None:
        logger.warning("event.conflict_weak_missing_event_id bay=%s", bay.code)
        return
    if event_service.already_processed(payload.event_id):
        return

    reservation = _open_reservation(bay)

    conflict = conflict_service.upsert_weak(
        bay=bay,
        reservation_id=reservation.id if reservation else None,
        source_event_id=payload.event_id,
        detected_at=payload.ts,
    )

    settings: Settings = current_app.config["APP_SETTINGS"]
    penalty_payment = None
    released_payment = None
    if reservation is not None and reservation.status in {
        ReservationStatus.ACTIVE,
        ReservationStatus.PENDING_CHECK_IN,
    }:
        reservation.status = ReservationStatus.IN_CONFLICT
        penalty_payment = payment_service.charge_penalty(
            reservation_id=reservation.id,
            penalty_kind=PenaltyKind.WEAK_CONFLICT,
            amount_cents=settings.penalty_cents,
            source_event_id=payload.event_id,
        )
        released_payment = payment_service.release(
            reservation_id=reservation.id, reason="remainder"
        )

    if bay.state != BayState.CONFLICT:
        old_state = bay.state
        bay.state = BayState.CONFLICT
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.STATE_CHANGED,
            from_state=old_state,
            to_state=BayState.CONFLICT,
            reservation_id=reservation.id if reservation else None,
        )

    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.CONFLICT_WEAK,
        reservation_id=reservation.id if reservation else None,
        source_event_id=payload.event_id,
        payload={"conflict_id": str(conflict.id)},
    )
    db.session.commit()

    notification_service.push_conflict_alert(conflict=conflict, bay=bay)
    notification_service.push_bay_updated(bay)
    if reservation is not None:
        publish_reservation_command(
            bay_code=bay.code,
            action="expire_check_in",
            reservation=reservation,
            user=reservation.user,
            bound_plates=plate_service.list_plate_strings(reservation.user_id),
        )
        notification_service.push_reservation_updated(reservation, bay)
        if released_payment is not None:
            notification_service.push_deposit_released(
                user=reservation.user,
                reservation=reservation,
                amount_cents=released_payment.amount_cents,
                reason="remainder",
            )
        if penalty_payment is not None:
            notification_service.push_penalty_captured(
                user=reservation.user,
                reservation=reservation,
                penalty_kind=PenaltyKind.WEAK_CONFLICT,
                amount_cents=penalty_payment.amount_cents,
            )


def _on_no_show(bay: ParkingBay, payload: EventPayload) -> None:
    """Pi `no_show`: reservation past arrival + grace, bay still empty."""
    if payload.event_id is None:
        logger.warning("event.no_show_missing_event_id bay=%s", bay.code)
        return
    if event_service.already_processed(payload.event_id):
        return

    reservation = _open_reservation(bay)
    if reservation is None or reservation.status not in {
        ReservationStatus.ACTIVE,
        ReservationStatus.PENDING_CHECK_IN,
    }:
        return

    reservation.status = ReservationStatus.EXPIRED_NO_SHOW
    if bay.current_reservation_id == reservation.id:
        bay.current_reservation_id = None
    if bay.state in {BayState.RESERVED, BayState.PENDING_CHECK_IN}:
        old_state = bay.state
        bay.state = BayState.AVAILABLE
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.STATE_CHANGED,
            from_state=old_state,
            to_state=BayState.AVAILABLE,
            reservation_id=reservation.id,
            payload={"reason": "no_show"},
        )

    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.NO_SHOW,
        reservation_id=reservation.id,
        source_event_id=payload.event_id,
    )

    settings: Settings = current_app.config["APP_SETTINGS"]
    penalty_payment = payment_service.charge_penalty(
        reservation_id=reservation.id,
        penalty_kind=PenaltyKind.NO_SHOW,
        amount_cents=settings.penalty_cents,
        source_event_id=payload.event_id,
    )
    released_payment = payment_service.release(reservation_id=reservation.id, reason="remainder")
    db.session.commit()

    publish_reservation_command(
        bay_code=bay.code,
        action="release",
        reservation=reservation,
        user=reservation.user,
        bound_plates=[],
        reason="no_show",
    )
    notification_service.push_bay_updated(bay)
    notification_service.push_reservation_updated(reservation, bay)
    if released_payment is not None:
        notification_service.push_deposit_released(
            user=reservation.user,
            reservation=reservation,
            amount_cents=released_payment.amount_cents,
            reason="remainder",
        )
    if penalty_payment is not None:
        notification_service.push_penalty_captured(
            user=reservation.user,
            reservation=reservation,
            penalty_kind=PenaltyKind.NO_SHOW,
            amount_cents=penalty_payment.amount_cents,
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _open_reservation(bay: ParkingBay) -> Reservation | None:
    return db.session.execute(
        select(Reservation)
        .where(
            Reservation.bay_id == bay.id,
            Reservation.status.in_(
                [
                    ReservationStatus.ACTIVE,
                    ReservationStatus.PENDING_CHECK_IN,
                    ReservationStatus.CHECKED_IN,
                    ReservationStatus.IN_CONFLICT,
                ]
            ),
        )
        .order_by(Reservation.booked_at.desc())
        .limit(1)
    ).scalar_one_or_none()


_HANDLERS = {
    "sensor_online": _on_sensor_online,
    "sensor_offline": _on_sensor_offline,
    "pending_check_in": _on_pending_check_in,
    "auto_check_in": _on_auto_check_in,
    "check_in_confirmed": _on_check_in_confirmed,
    "conflict_strong": _on_conflict_strong,
    "conflict_weak": _on_conflict_weak,
    "no_show": _on_no_show,
}
