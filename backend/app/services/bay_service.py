"""Bay-state mirror service.

The Pi owns the per-bay state machine; this service only
*mirrors* the value the Pi reports. ``apply_state`` is the single code path
that writes ``parking_bays.state`` and always produces a ``bay_events`` row in
the same transaction.

Three inferences run on a state change:

* **Reservation completion** — when the previous state was a held-by-user
  state (``reserved_checked_in`` / ``pending_check_in``) and the new state is
  ``available``, any open ``CHECKED_IN`` / ``PENDING_CHECK_IN`` /
  ``IN_CONFLICT`` reservation is closed as ``COMPLETED``.
* **Strong-conflict restore** — when the previous state was ``conflict`` and
  the open conflict on this bay is ``kind='strong'`` with a still-open
  reservation (``ACTIVE`` / ``CHECKED_IN`` / ``PENDING_CHECK_IN``), the wrong
  vehicle has driven away. The conflict resolves as ``vehicle_left``, the bay
  mirror is locally flipped back to ``RESERVED`` / ``RESERVED_CHECKED_IN`` so
  the no-show sweeper doesn't trip on the transient ``AVAILABLE``, and the
  reservation cache is republished to the Pi. No refund, no release — the
  reservation simply resumes. A ``PENDING_CHECK_IN`` reservation is rolled
  back to ``ACTIVE`` (the holder hasn't actually arrived). Handles both
  ``CONFLICT → AVAILABLE`` and the Pi-skipped ``CONFLICT → RESERVED``
  transition.
* **Pending-check-in rollback** — when the previous state was
  ``pending_check_in`` and the bay returns directly to ``reserved`` (an
  unknown vehicle arrived and left without LPR ever firing a
  ``conflict_strong``), the open ``PENDING_CHECK_IN`` reservation is rolled
  back to ``ACTIVE`` and the Pi reservation cache is republished. Without
  this the reservation would stay stuck in ``PENDING_CHECK_IN`` forever.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models import (
    BayEventKind,
    BayState,
    Conflict,
    ConflictKind,
    ConflictResolution,
    ParkingBay,
    Reservation,
    ReservationStatus,
    SensorReading,
)
from app.mqtt.topics import ReservationActionLiteral, ReservationReleaseReason, StatePayload
from app.services import event_service, payment_service, plate_service
from app.services.mqtt_publisher import publish_reservation_command
from app.services.notification_service import (
    push_bay_updated,
    push_conflict_resolved,
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

        # Strong-conflict restore takes precedence over completion: if the
        # bay just emptied because the wrong vehicle drove away, the
        # reservation continues and must not be marked COMPLETED.
        restored = _maybe_restore_after_strong_conflict(
            bay, old_state=old_state, new_state=new_state
        )
        if restored is not None:
            db.session.commit()
            push_bay_updated(bay)
            push_conflict_resolved(conflict=restored.conflict, bay=bay)
            push_reservation_updated(restored.reservation, bay)
            publish_reservation_command(
                bay_code=bay.code,
                action=restored.publish_action,
                reservation=restored.reservation,
                user=restored.reservation.user,
                bound_plates=plate_service.list_plate_strings(restored.reservation.user_id),
            )
            return

        # No-conflict rollback: an unknown vehicle visited the bay
        # (PENDING_CHECK_IN) and left without LPR ever firing
        # `conflict_strong`. Roll the reservation back to ACTIVE so the
        # holder can still arrive.
        rolled_back = _maybe_rollback_pending_check_in(
            bay, old_state=old_state, new_state=new_state
        )
        if rolled_back is not None:
            db.session.commit()
            push_bay_updated(bay)
            push_reservation_updated(rolled_back, bay)
            publish_reservation_command(
                bay_code=bay.code,
                action="create",
                reservation=rolled_back,
                user=rolled_back.user,
                bound_plates=plate_service.list_plate_strings(rolled_back.user_id),
            )
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


@dataclass
class _StrongConflictRestore:
    conflict: Conflict
    reservation: Reservation
    publish_action: ReservationActionLiteral


def _maybe_restore_after_strong_conflict(
    bay: ParkingBay, *, old_state: BayState, new_state: BayState
) -> _StrongConflictRestore | None:
    """``CONFLICT → {AVAILABLE, RESERVED}`` with an open strong conflict +
    open reservation means the wrong vehicle drove away. Resolve the conflict
    as ``vehicle_left`` and resume the reservation; do **not** complete it.

    Accepts the Pi-skipped ``CONFLICT → RESERVED`` transition (when the
    sensor jumps straight to "empty + held") in addition to the canonical
    ``CONFLICT → AVAILABLE``.

    Returns the restored reservation + conflict + republish action so the
    caller can fire the matching Pi command and notifications. Returns
    ``None`` when this is *not* a strong-restore situation (no open
    conflict, weak conflict, or reservation not in a resumable status) —
    completion inference will then run on its usual rules.
    """
    if old_state != BayState.CONFLICT:
        return None
    if new_state not in {BayState.AVAILABLE, BayState.RESERVED, BayState.RESERVED_CHECKED_IN}:
        return None

    # At most one unresolved conflict per bay (partial unique index
    # `conflicts_one_open_per_bay`); fetch it cheaply.
    conflict = db.session.execute(
        select(Conflict).where(
            Conflict.bay_id == bay.id,
            Conflict.resolved_at.is_(None),
        )
    ).scalar_one_or_none()
    if conflict is None or conflict.kind != ConflictKind.STRONG:
        return None
    if conflict.reservation_id is None:
        return None

    reservation = db.session.get(Reservation, conflict.reservation_id)
    if reservation is None:
        return None
    # Strong-conflict resumable statuses: ACTIVE (vehicle hadn't arrived, or
    # already rolled back from PENDING_CHECK_IN by the conflict_strong
    # handler), CHECKED_IN (incident layered on a live session), or
    # PENDING_CHECK_IN (defensive: the rollback step in the conflict_strong
    # handler didn't run — e.g. the conflict_strong event was dropped or
    # arrived out of order. Treat as ACTIVE since the wrong vehicle is now
    # confirmed gone). IN_CONFLICT belongs to weak only.
    if reservation.status in {ReservationStatus.ACTIVE, ReservationStatus.PENDING_CHECK_IN}:
        if reservation.status == ReservationStatus.PENDING_CHECK_IN:
            reservation.status = ReservationStatus.ACTIVE
            reservation.check_in_grace_expires_at = None
        now_ = utcnow()
        if reservation.expected_arrival_time < now_:
            reservation.expected_arrival_time = now_
        target_state = BayState.RESERVED
        publish_action: ReservationActionLiteral = "create"
    elif reservation.status == ReservationStatus.CHECKED_IN:
        target_state = BayState.RESERVED_CHECKED_IN
        publish_action = "check_in"
    else:
        return None

    now = utcnow()
    conflict.resolved_at = now
    conflict.resolution = ConflictResolution.VEHICLE_LEFT

    # Flip the bay mirror locally back to RESERVED/RESERVED_CHECKED_IN so the
    # UI and admin tooling see the resumed reservation immediately rather than
    # the transient AVAILABLE. Pi's next /state message will idempotently
    # reconcile back to whatever the sensor actually reports.
    if bay.state != target_state:
        # Only record the synthetic transition when we actually flip — for
        # CONFLICT → RESERVED the Pi already reported `target_state`, so the
        # row recorded in `apply_state` is sufficient.
        from_state = bay.state
        bay.state = target_state
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.STATE_CHANGED,
            from_state=from_state,
            to_state=target_state,
            reservation_id=reservation.id,
            payload={"reason": "strong_conflict_cleared"},
        )
    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.CONFLICT_RESOLVED,
        reservation_id=reservation.id,
        payload={
            "conflict_id": str(conflict.id),
            "resolution": ConflictResolution.VEHICLE_LEFT.value,
        },
    )
    return _StrongConflictRestore(
        conflict=conflict,
        reservation=reservation,
        publish_action=publish_action,
    )


def _maybe_rollback_pending_check_in(
    bay: ParkingBay, *, old_state: BayState, new_state: BayState
) -> Reservation | None:
    """``PENDING_CHECK_IN → RESERVED`` with an open ``PENDING_CHECK_IN``
    reservation: an unknown vehicle arrived and left without LPR ever firing
    a ``conflict_strong`` (so the conflict-restore path didn't run). Roll
    the reservation back to ``ACTIVE`` so the holder can still arrive.

    Returns the rolled-back reservation so the caller can republish the
    ``create`` command to the Pi and notify the holder. Returns ``None``
    when this is not a rollback situation — the standard completion
    inference (``PENDING_CHECK_IN → AVAILABLE``) is unchanged.
    """
    if old_state != BayState.PENDING_CHECK_IN or new_state != BayState.RESERVED:
        return None

    reservation = db.session.execute(
        select(Reservation).where(
            Reservation.bay_id == bay.id,
            Reservation.status == ReservationStatus.PENDING_CHECK_IN,
        )
    ).scalar_one_or_none()
    if reservation is None:
        return None

    reservation.status = ReservationStatus.ACTIVE
    reservation.check_in_grace_expires_at = None
    # No synthetic STATE_CHANGED row: `apply_state` already records the
    # Pi-reported PENDING_CHECK_IN → RESERVED transition. This rollback is
    # purely a reservation-status change.
    return reservation


def _maybe_complete_reservation(
    bay: ParkingBay, *, old_state: BayState, new_state: BayState
) -> Reservation | None:
    """When a bay transitions from a reservation-active state back to
    ``available``, infer the held reservation has ended and mark it
    ``COMPLETED``. Idempotent — only fires when there is an open
    ``CHECKED_IN`` / ``PENDING_CHECK_IN`` reservation to close.

    Note: ``CONFLICT → AVAILABLE`` with a strong restore is handled by
    :func:`_maybe_restore_after_strong_conflict` *before* this runs, so
    weak-conflict bays are the only remaining ``CONFLICT → AVAILABLE``
    case that lands here.
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
