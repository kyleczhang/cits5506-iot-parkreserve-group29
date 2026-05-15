"""Reservation business rules.

Owned by the backend; the Pi owns the per-bay state machine. This service:

  * enforces the 1-hour booking window (R11)
  * gates booking on a successful mock-payment pre-auth (R20)
  * rejects users with zero bound plates (auto check-in is impossible — R15)
  * publishes ``cloud/bay/<code>/reservation`` *with* the user's bound plates
  * on a late cancel (< 15 min to arrival) captures a ``late_cancel``
    penalty against the deposit and releases the remainder; on a clean
    cancel, releases the full deposit
  * accepts user-initiated check-ins (QR / manual fallback) in
    ``PENDING_CHECK_IN`` and in ``IN_CONFLICT`` when the open conflict is
    weak and unresolved — auto check-ins via LPR enter through the event
    handler, not this service
  * is the only writer of ``parking_bays.current_reservation_id``

Reservations transition to ``COMPLETED`` via inference in
:mod:`app.services.bay_service` (no Pi event for "session ended"); the
release of the deposit on completion happens there too.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.extensions import db
from app.models import (
    BayEventKind,
    BayState,
    CheckInMechanism,
    Conflict,
    ConflictKind,
    ConflictResolution,
    ParkingBay,
    PenaltyKind,
    Reservation,
    ReservationStatus,
    User,
    UserRole,
)
from app.schemas.payment import CardDetails
from app.services import (
    bay_service,
    event_service,
    payment_service,
    plate_service,
)
from app.services.mqtt_publisher import publish_reservation_command
from app.services.notification_service import (
    push_bay_updated,
    push_conflict_resolved,
    push_deposit_released,
    push_penalty_captured,
    push_refund_issued,
    push_reservation_updated,
)
from app.utils.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def _settings() -> Settings:
    return current_app.config["APP_SETTINGS"]


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create(
    *,
    user: User,
    bay_code: str,
    expected_arrival_time: datetime,
    card: CardDetails,
    now: datetime | None = None,
) -> tuple[Reservation, int]:
    """Reserve a bay with a deposit pre-auth (R20).

    Returns ``(reservation, deposit_cents)``. Booking transaction is
    atomic: if card validation, expiry check, or balance check fails the
    reservation row is never inserted.
    """
    settings = _settings()
    now = now or utcnow()

    delta = (expected_arrival_time - now).total_seconds()
    if delta <= 0:
        raise ValidationError(
            "expected_arrival_time must be in the future",
            code="invalid_arrival_time",
        )
    if delta > settings.booking_window_minutes * 60:
        raise ValidationError(
            f"reservations must be at most {settings.booking_window_minutes} min in advance",
            code="outside_booking_window",
        )

    bound_plates = plate_service.list_plate_strings(user.id)
    if not bound_plates:
        raise ValidationError(
            "bind at least one licence plate before reserving",
            code="no_bound_plates",
        )

    bay = bay_service.get_by_code(bay_code)
    _assert_bay_reservable(bay)

    # Validate + lock the card BEFORE inserting the reservation. If validation
    # fails (or balance is insufficient) the transaction is rolled back and
    # no orphan reservation is left behind (R20).
    mock_card = payment_service.validate_card(card)

    reservation = Reservation(
        bay_id=bay.id,
        user_id=user.id,
        status=ReservationStatus.ACTIVE,
        expected_arrival_time=expected_arrival_time,
    )
    db.session.add(reservation)
    try:
        db.session.flush()
    except IntegrityError as err:
        db.session.rollback()
        raise ConflictError(
            f"bay {bay_code} already has an open reservation",
            code="reservation_already_active",
        ) from err

    try:
        payment_service.preauthorize(
            reservation_id=reservation.id,
            user_id=user.id,
            card=mock_card,
            amount_cents=settings.deposit_cents,
        )
    except Exception:
        db.session.rollback()
        raise

    bay.current_reservation_id = reservation.id
    bay.state = BayState.RESERVED
    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.RESERVATION_CREATED,
        from_state=BayState.AVAILABLE,
        to_state=BayState.RESERVED,
        reservation_id=reservation.id,
        payload={"expected_arrival_time": expected_arrival_time.isoformat()},
    )
    db.session.commit()

    publish_reservation_command(
        bay_code=bay.code,
        action="create",
        reservation=reservation,
        user=user,
        bound_plates=bound_plates,
    )
    push_reservation_updated(reservation, bay)
    push_bay_updated(bay)
    return reservation, settings.deposit_cents


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


def cancel(*, user: User, reservation_id: UUID, now: datetime | None = None) -> Reservation:
    reservation = _require_own(user, reservation_id)
    settings = _settings()
    now = now or utcnow()

    if reservation.status in {
        ReservationStatus.CANCELLED,
        ReservationStatus.CANCELLED_LATE,
    }:
        return reservation  # idempotent

    if reservation.status not in {
        ReservationStatus.ACTIVE,
        ReservationStatus.PENDING_CHECK_IN,
    }:
        raise ConflictError(
            f"reservation is {reservation.status.value}, cannot cancel",
            code="reservation_not_cancellable",
        )

    # No-fault branch: the holder is the victim of an unresolved *strong*
    # conflict (a wrong vehicle is physically occupying their bay). Routing
    # this through the normal late-cancel path would charge a penalty for a
    # situation the user didn't cause and would also leave the open conflict
    # row dangling. Refund in full, resolve the conflict, and leave bay state
    # for the Pi's next /state — the wrong vehicle is still there, so we
    # must not invent a phantom AVAILABLE.
    open_strong_conflict = db.session.execute(
        select(Conflict).where(
            Conflict.reservation_id == reservation.id,
            Conflict.resolved_at.is_(None),
            Conflict.kind == ConflictKind.STRONG,
        )
    ).scalar_one_or_none()
    if open_strong_conflict is not None:
        return _cancel_no_fault_under_strong_conflict(
            user=user,
            reservation=reservation,
            conflict=open_strong_conflict,
            now=now,
        )

    cutoff = settings.late_cancel_cutoff_minutes * 60
    is_late = (reservation.expected_arrival_time - now).total_seconds() < cutoff

    reservation.status = (
        ReservationStatus.CANCELLED_LATE if is_late else ReservationStatus.CANCELLED
    )
    reservation.cancelled_at = now

    bay = reservation.bay
    if bay.current_reservation_id == reservation.id:
        bay.current_reservation_id = None

    # Free the bay locally — Pi will echo with its authoritative state on the
    # next /state message; until then we trust this transition.
    if bay.state in {
        BayState.RESERVED,
        BayState.PENDING_CHECK_IN,
    }:
        old_state = bay.state
        bay.state = BayState.AVAILABLE
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.STATE_CHANGED,
            from_state=old_state,
            to_state=BayState.AVAILABLE,
            reservation_id=reservation.id,
            payload={"reason": "cancel"},
        )
    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.RESERVATION_CANCELLED,
        reservation_id=reservation.id,
        payload={"late": is_late},
    )

    release_reason: str
    if is_late:
        penalty_payment = payment_service.charge_penalty(
            reservation_id=reservation.id,
            penalty_kind=PenaltyKind.LATE_CANCEL,
            amount_cents=settings.penalty_cents,
        )
        release_reason = "remainder"
        released_payment = payment_service.release(
            reservation_id=reservation.id, reason=release_reason
        )
    else:
        penalty_payment = None
        release_reason = "clean_cancel"
        released_payment = payment_service.release(
            reservation_id=reservation.id, reason=release_reason
        )

    db.session.commit()

    publish_reservation_command(
        bay_code=bay.code,
        action="cancel",
        reservation=reservation,
        user=user,
        bound_plates=plate_service.list_plate_strings(user.id),
    )
    push_reservation_updated(reservation, bay)
    push_bay_updated(bay)
    if released_payment is not None:
        push_deposit_released(
            user=user,
            reservation=reservation,
            amount_cents=released_payment.amount_cents,
            reason=release_reason,
        )
    if penalty_payment is not None:
        push_penalty_captured(
            user=user,
            reservation=reservation,
            penalty_kind=PenaltyKind.LATE_CANCEL,
            amount_cents=penalty_payment.amount_cents,
        )
    return reservation


def _cancel_no_fault_under_strong_conflict(
    *,
    user: User,
    reservation: Reservation,
    conflict: Conflict,
    now: datetime,
) -> Reservation:
    """Cancel branch for "wrong vehicle is in my bay; let me out, no charge."

    Mirrors the relevant pieces of :func:`admin_terminate` — full refund,
    conflict resolved, ``release(reason="admin_override")`` published — but
    leaves ``bay.state`` untouched. The wrong vehicle is still physically
    present, so flipping the mirror to ``AVAILABLE`` here would mis-advertise
    a free bay; the Pi's next ``/state`` will reconcile when the wrong
    vehicle eventually leaves.
    """
    bay = reservation.bay

    conflict.resolved_at = now
    conflict.resolution = ConflictResolution.USER_CANCELLED

    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = now
    if bay.current_reservation_id == reservation.id:
        bay.current_reservation_id = None

    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.RESERVATION_CANCELLED,
        reservation_id=reservation.id,
        payload={"reason": "user_cancel_under_strong_conflict"},
    )
    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.CONFLICT_RESOLVED,
        reservation_id=reservation.id,
        payload={
            "conflict_id": str(conflict.id),
            "resolution": ConflictResolution.USER_CANCELLED.value,
        },
    )

    refund_payment = payment_service.refund(reservation_id=reservation.id)

    db.session.commit()

    publish_reservation_command(
        bay_code=bay.code,
        action="release",
        reservation=reservation,
        user=user,
        bound_plates=plate_service.list_plate_strings(user.id),
        reason="admin_override",
    )
    push_conflict_resolved(conflict=conflict, bay=bay)
    push_reservation_updated(reservation, bay)
    push_bay_updated(bay)
    if refund_payment is not None:
        push_refund_issued(
            user=user,
            reservation=reservation,
            amount_cents=refund_payment.amount_cents,
        )
    return reservation


# ---------------------------------------------------------------------------
# User-initiated check-in (QR / manual fallback only)
# ---------------------------------------------------------------------------


def check_in(
    *,
    user: User,
    reservation_id: UUID,
    bay_code: str,
    source: CheckInMechanism,
    now: datetime | None = None,
) -> Reservation:
    if source not in {CheckInMechanism.QR, CheckInMechanism.MANUAL}:
        raise ValidationError(
            "user-initiated check-in source must be 'qr' or 'manual'",
            code="invalid_check_in_source",
        )

    reservation = _require_own(user, reservation_id)
    now = now or utcnow()

    if reservation.bay.code != bay_code:
        raise ValidationError(
            "bay_code does not match this reservation",
            code="bay_code_mismatch",
        )

    if reservation.status == ReservationStatus.CHECKED_IN:
        return reservation  # idempotent

    if reservation.status == ReservationStatus.ACTIVE:
        raise ConflictError(
            "vehicle has not been detected at this bay yet",
            code="vehicle_not_detected_yet",
        )

    conflict_to_resolve: Conflict | None = None
    if reservation.status == ReservationStatus.IN_CONFLICT:
        conflict_to_resolve = db.session.execute(
            select(Conflict).where(
                Conflict.bay_id == reservation.bay_id,
                Conflict.reservation_id == reservation.id,
                Conflict.resolved_at.is_(None),
            )
        ).scalar_one_or_none()
        if conflict_to_resolve is None or conflict_to_resolve.kind != ConflictKind.WEAK:
            raise ConflictError(
                "this reservation is in conflict; manual check-in is not allowed",
                code="reservation_in_conflict",
            )

    elif reservation.status != ReservationStatus.PENDING_CHECK_IN:
        raise ConflictError(
            f"reservation is {reservation.status.value}, cannot check in",
            code="reservation_not_checkinable",
        )

    reservation.status = ReservationStatus.CHECKED_IN
    reservation.checked_in_at = now
    reservation.check_in_mechanism = source
    reservation.check_in_recognised_plate = None  # qr/manual carry no plate (CHECK constraint)
    if conflict_to_resolve is not None:
        conflict_to_resolve.resolution = ConflictResolution.USER_ARRIVED_AND_CHECKED_IN
        conflict_to_resolve.resolved_at = now

    bay = reservation.bay
    old_state = bay.state
    bay.state = BayState.RESERVED_CHECKED_IN
    event_service.record(
        bay_id=bay.id,
        kind=BayEventKind.STATE_CHANGED,
        from_state=old_state,
        to_state=BayState.RESERVED_CHECKED_IN,
        reservation_id=reservation.id,
        payload={"check_in_source": source.value},
    )
    db.session.commit()

    publish_reservation_command(
        bay_code=bay.code,
        action="check_in",
        reservation=reservation,
        user=user,
        bound_plates=plate_service.list_plate_strings(user.id),
    )
    push_reservation_updated(reservation, bay)
    push_bay_updated(bay)
    return reservation


# ---------------------------------------------------------------------------
# Admin termination (facility-side cancellation + refund)
# ---------------------------------------------------------------------------


_TERMINAL_RESERVATION_STATUSES = {
    ReservationStatus.CANCELLED,
    ReservationStatus.CANCELLED_LATE,
    ReservationStatus.COMPLETED,
    ReservationStatus.EXPIRED_NO_SHOW,
}

# Bay states whose physical occupancy belongs to the holder (no other
# vehicle is present). Safe to flip back to AVAILABLE locally on admin
# termination — the Pi's next ``/state`` will idempotently reconcile.
_HOLDER_OWNED_BAY_STATES = {
    BayState.RESERVED,
    BayState.PENDING_CHECK_IN,
    BayState.RESERVED_CHECKED_IN,
}


def admin_terminate(
    *,
    admin: User,
    reservation_id: UUID,
    now: datetime | None = None,
) -> Reservation:
    """Admin-initiated termination of a reservation.

    This is the *only* path that issues a refund on a strong-conflict
    reservation. The ``conflict_strong`` event itself never refunds — see
    [event_dispatcher._on_conflict_strong][app.services.event_dispatcher].

    Bay-mirror release is **narrowed** to states the holder genuinely
    owns. CONFLICT + STRONG / OCCUPIED / OFFLINE deliberately leave
    ``bay.state`` alone — flipping AVAILABLE there would either advertise
    a bay that's still physically blocked by the wrong vehicle (strong
    conflict) or fight the Pi's authoritative state. ``CONFLICT + WEAK`` is
    treated as holder-owned because weak conflicts are a deferred user
    breach with no third-party vehicle present.

    Reservations that are already terminal still pass through the conflict
    cleanup branch when an open conflict remains — otherwise an unresolved
    ``conflicts`` row could outlive the reservation forever.

    Steps:

    1. Verify ``admin`` carries the ``admin`` role.
    2. If the reservation is terminal *and* no open conflict remains:
       short-circuit (true idempotent no-op).
    3. Resolve any open conflict tied to this reservation as
       ``admin_resolved`` and emit a ``CONFLICT_RESOLVED`` audit row.
    4. If the reservation is still active: mark ``CANCELLED``, release the
       bay mirror per the rules above, refund the remaining deposit, and
       publish ``release(reason="admin_override")``.
    5. Push the appropriate notifications.
    """
    if admin.role != UserRole.ADMIN:
        raise ForbiddenError(
            "only admins may force-terminate a reservation",
            code="admin_only",
        )

    reservation = db.session.execute(
        select(Reservation)
        .where(Reservation.id == reservation_id)
        .with_for_update()
    ).scalar_one_or_none()
    if reservation is None:
        raise NotFoundError("reservation not found", code="reservation_not_found")

    open_conflict = db.session.execute(
        select(Conflict).where(
            Conflict.reservation_id == reservation.id,
            Conflict.resolved_at.is_(None),
        )
    ).scalar_one_or_none()

    is_terminal = reservation.status in _TERMINAL_RESERVATION_STATUSES
    if is_terminal and open_conflict is None:
        return reservation  # idempotent — nothing left to do

    now = now or utcnow()
    bay = reservation.bay

    # Conflict cleanup runs in either branch — orphaned conflicts on a
    # terminal reservation still need to be closed so the partial unique
    # index on `conflicts_one_open_per_bay` doesn't trap future bookings.
    if open_conflict is not None:
        open_conflict.resolved_at = now
        open_conflict.resolution = ConflictResolution.ADMIN_RESOLVED
        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.CONFLICT_RESOLVED,
            reservation_id=reservation.id,
            payload={
                "conflict_id": str(open_conflict.id),
                "resolution": ConflictResolution.ADMIN_RESOLVED.value,
                "admin_id": str(admin.id),
            },
        )

    refund_payment = None
    publish_release = False
    if not is_terminal:
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = now

        if bay.current_reservation_id == reservation.id:
            bay.current_reservation_id = None

        flip_to_available = bay.state in _HOLDER_OWNED_BAY_STATES or (
            bay.state == BayState.CONFLICT
            and open_conflict is not None
            and open_conflict.kind == ConflictKind.WEAK
        )
        if flip_to_available:
            old_bay_state = bay.state
            bay.state = BayState.AVAILABLE
            event_service.record(
                bay_id=bay.id,
                kind=BayEventKind.STATE_CHANGED,
                from_state=old_bay_state,
                to_state=BayState.AVAILABLE,
                reservation_id=reservation.id,
                payload={"reason": "admin_terminate"},
            )

        event_service.record(
            bay_id=bay.id,
            kind=BayEventKind.RESERVATION_CANCELLED,
            reservation_id=reservation.id,
            payload={"reason": "admin_terminate", "admin_id": str(admin.id)},
        )

        refund_payment = payment_service.refund(reservation_id=reservation.id)
        publish_release = True

    db.session.commit()

    if publish_release:
        publish_reservation_command(
            bay_code=bay.code,
            action="release",
            reservation=reservation,
            user=reservation.user,
            bound_plates=[],
            reason="admin_override",
        )
    if open_conflict is not None:
        push_conflict_resolved(conflict=open_conflict, bay=bay)
    if not is_terminal:
        push_reservation_updated(reservation, bay)
    push_bay_updated(bay)
    if refund_payment is not None:
        push_refund_issued(
            user=reservation.user,
            reservation=reservation,
            amount_cents=refund_payment.amount_cents,
        )
    return reservation


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def list_for_user(user: User) -> list[Reservation]:
    return list(
        db.session.execute(
            select(Reservation)
            .where(Reservation.user_id == user.id)
            .order_by(Reservation.booked_at.desc())
        ).scalars()
    )


def get_by_id(reservation_id: UUID) -> Reservation:
    res = db.session.get(Reservation, reservation_id)
    if res is None:
        raise NotFoundError("reservation not found", code="reservation_not_found")
    return res


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _require_own(user: User, reservation_id: UUID) -> Reservation:
    res = get_by_id(reservation_id)
    if res.user_id != user.id and user.role.value != "admin":
        raise ForbiddenError("reservation belongs to another user", code="forbidden")
    return res


def _assert_bay_reservable(bay: ParkingBay) -> None:
    if bay.state == BayState.OFFLINE:
        raise ConflictError(
            f"bay {bay.code} is offline",
            code="bay_offline",
        )
    if bay.state in {BayState.OCCUPIED, BayState.CONFLICT}:
        raise ConflictError(
            f"bay {bay.code} is not available (state={bay.state.value})",
            code="bay_not_available",
        )
    # AVAILABLE — accepted; RESERVED / PENDING_CHECK_IN / RESERVED_CHECKED_IN
    # are caught by the partial unique index `reservations_one_open_per_bay`
    # and translated to 409 in `create`.
