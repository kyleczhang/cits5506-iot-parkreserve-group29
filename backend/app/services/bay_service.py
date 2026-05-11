"""Bay-state mirror service.

The Pi owns the per-bay state machine; this service only
*mirrors* the value the Pi reports. ``apply_state`` is the single code path
that writes ``parking_bays.state`` and always produces a ``bay_events`` row in
the same transaction.

It also infers reservation completion: when a bay transitions back to
``available`` while an active ``CHECKED_IN`` reservation exists, we mark the
reservation ``COMPLETED`` (the Pi has no dedicated session-end event — see
the bay returning to ``available`` as the end of the parking session).
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models import (
    BayEventKind,
    BayState,
    ParkingBay,
    Reservation,
    ReservationStatus,
    SensorReading,
)
from app.mqtt.topics import ReservationReleaseReason, StatePayload
from app.services import event_service, payment_service
from app.services.mqtt_publisher import publish_reservation_command
from app.services.notification_service import (
    push_bay_updated,
    push_deposit_released,
    push_reservation_updated,
)
from app.utils.errors import NotFoundError
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def get_by_code(code: str) -> ParkingBay:
    bay = db.session.execute(select(ParkingBay).where(ParkingBay.code == code)).scalar_one_or_none()
    if bay is None:
        raise NotFoundError(f"bay {code!r} does not exist", code="bay_not_found")
    return bay


def list_all() -> list[ParkingBay]:
    return list(db.session.execute(select(ParkingBay).order_by(ParkingBay.code)).scalars())


def apply_state(*, bay_code: str, payload: StatePayload) -> None:
    """Mirror the bay state reported by the Pi.

    Writes one ``sensor_readings`` row, updates ``parking_bays.state`` to the
    Pi-supplied value, and records exactly one ``bay_events`` row (idempotent
    on ``source_event_id``). Also infers ``COMPLETED`` reservations on a
    ``reserved_checked_in → available`` transition.
    """
    bay = db.session.execute(
        select(ParkingBay).where(ParkingBay.code == bay_code)
    ).scalar_one_or_none()
    if bay is None:
        logger.warning("bay.apply_state_unknown code=%s", bay_code)
        return

    new_state = BayState(payload.state)
    old_state = bay.state

    distance = Decimal(str(payload.last_distance_cm))
    db.session.add(
        SensorReading(
            bay_id=bay.id,
            distance_cm=distance,
            occupied=new_state
            in {
                BayState.OCCUPIED,
                BayState.PENDING_CHECK_IN,
                BayState.RESERVED_CHECKED_IN,
                BayState.CONFLICT,
            },
            recorded_at=payload.ts,
        )
    )

    bay.last_distance_cm = distance
    bay.sensor_last_seen_at = payload.ts

    if new_state != old_state:
        bay.state = new_state
        event = event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.STATE_CHANGED,
            from_state=old_state,
            to_state=new_state,
            source_event_id=payload.event_id,
            payload={"distance_cm": float(payload.last_distance_cm)},
        )
        if event is None:
            # Replay — silently drop side-effects, the original handling
            # already produced the necessary state and notifications.
            db.session.rollback()
            return

        completed_reservation = _maybe_complete_reservation(
            bay, old_state=old_state, new_state=new_state
        )
        release_payment = None
        release_reason = None
        if completed_reservation is not None:
            release_payment = payment_service.release(
                reservation_id=completed_reservation.id,
                reason="completed",
            )
            release_reason = _release_reason_for_completion(old_state)

        db.session.commit()

        push_bay_updated(bay)
        if completed_reservation is not None:
            publish_reservation_command(
                bay_code=bay.code,
                action="release",
                reservation=completed_reservation,
                user=completed_reservation.user,
                bound_plates=[],
                reason=release_reason,
            )
            push_reservation_updated(completed_reservation, bay)
            if release_payment is not None:
                push_deposit_released(
                    user=completed_reservation.user,
                    reservation=completed_reservation,
                    amount_cents=release_payment.amount_cents,
                    reason="completed",
                )
        return

    db.session.commit()
    push_bay_updated(bay)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _maybe_complete_reservation(
    bay: ParkingBay, *, old_state: BayState, new_state: BayState
) -> Reservation | None:
    """When a bay transitions from a reservation-active state back to
    ``available``, infer the held reservation has ended and mark it
    ``COMPLETED``. Idempotent — only fires when there is an open
    ``CHECKED_IN`` / ``PENDING_CHECK_IN`` reservation to close.
    """
    if new_state != BayState.AVAILABLE:
        return None
    if old_state not in {
        BayState.RESERVED_CHECKED_IN,
        BayState.PENDING_CHECK_IN,
        BayState.CONFLICT,
    }:
        return None

    reservation = db.session.execute(
        select(Reservation).where(
            Reservation.bay_id == bay.id,
            Reservation.status.in_(
                [
                    ReservationStatus.CHECKED_IN,
                    ReservationStatus.PENDING_CHECK_IN,
                    ReservationStatus.IN_CONFLICT,
                ]
            ),
        )
    ).scalar_one_or_none()
    if reservation is None:
        return None

    reservation.status = ReservationStatus.COMPLETED
    reservation.completed_at = utcnow()
    if bay.current_reservation_id == reservation.id:
        bay.current_reservation_id = None
    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.RESERVATION_COMPLETED,
        reservation_id=reservation.id,
        payload={"reason": "bay_freed"},
    )
    return reservation


def _release_reason_for_completion(old_state: BayState) -> ReservationReleaseReason:
    if old_state == BayState.RESERVED_CHECKED_IN:
        return "completed"
    return "abandoned"
