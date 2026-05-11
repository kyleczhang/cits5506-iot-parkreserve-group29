"""User-facing notifications.

Thin abstraction with two drivers:

- WebSocket (always-on; in-app toasts and dashboard updates)
- Web-push / email (out of core scope — stub logger here)

The two reservation-holder call-sites are :func:`push_auto_check_in` and
:func:`push_pending_check_in`. Admin alerts go to :func:`push_conflict_alert`.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models import (
    Conflict,
    LicencePlate,
    ParkingBay,
    PenaltyKind,
    Reservation,
    User,
)
from app.sockets.events import (
    emit_bay_updated,
    emit_conflict,
    emit_payment_deposit_released,
    emit_payment_penalty_captured,
    emit_payment_refunded,
    emit_plate_updated,
    emit_reservation_auto_checked_in,
    emit_reservation_pending_check_in,
    emit_reservation_updated,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bay + reservation generic updates
# ---------------------------------------------------------------------------


def push_bay_updated(bay: ParkingBay) -> None:
    emit_bay_updated(bay)


def push_reservation_updated(reservation: Reservation, bay: ParkingBay) -> None:
    emit_reservation_updated(reservation, bay)


def push_plate_updated(user: User, plates: list[LicencePlate]) -> None:
    emit_plate_updated(user, plates)


# ---------------------------------------------------------------------------
# Reservation-holder notifications
# ---------------------------------------------------------------------------


def push_auto_check_in(
    *, user: User, bay: ParkingBay, reservation: Reservation, recognised_plate: str
) -> None:
    """Dashboard prompt on `auto_check_in` — "you're checked in at Bay X"."""
    emit_reservation_auto_checked_in(reservation, bay, recognised_plate)
    logger.info(
        "notify.auto_check_in user=%s bay=%s plate=%s",
        user.id,
        bay.code,
        recognised_plate,
    )


def push_pending_check_in(*, user: User, bay: ParkingBay, reservation: Reservation) -> None:
    """Dashboard prompt on `pending_check_in` — "please check in manually"."""
    emit_reservation_pending_check_in(reservation, bay)
    logger.info(
        "notify.pending_check_in user=%s bay=%s reservation=%s",
        user.id,
        bay.code,
        reservation.id,
    )


# ---------------------------------------------------------------------------
# Admin notifications
# ---------------------------------------------------------------------------


def push_conflict_alert(*, conflict: Conflict, bay: ParkingBay) -> None:
    """Admin alert on `conflict_strong` / `conflict_weak`."""
    emit_conflict(bay, conflict, raised=True)
    logger.warning(
        "notify.conflict kind=%s bay=%s plate=%s",
        conflict.kind.value,
        bay.code,
        conflict.recognised_plate,
    )


def push_conflict_resolved(*, conflict: Conflict, bay: ParkingBay) -> None:
    emit_conflict(bay, conflict, raised=False)


# ---------------------------------------------------------------------------
# Payment notifications
# ---------------------------------------------------------------------------


def push_deposit_released(
    *, user: User, reservation: Reservation, amount_cents: int, reason: str
) -> None:
    """`payment.deposit_released` — clean cancel or normal completion."""
    emit_payment_deposit_released(reservation, amount_cents, reason)
    logger.info(
        "notify.deposit_released user=%s reservation=%s amount=%d reason=%s",
        user.id,
        reservation.id,
        amount_cents,
        reason,
    )


def push_refund_issued(*, user: User, reservation: Reservation, amount_cents: int) -> None:
    """`payment.refunded` — strong-conflict victim refund."""
    emit_payment_refunded(reservation, amount_cents)
    logger.info(
        "notify.refund_issued user=%s reservation=%s amount=%d",
        user.id,
        reservation.id,
        amount_cents,
    )


def push_penalty_captured(
    *,
    user: User,
    reservation: Reservation,
    penalty_kind: PenaltyKind,
    amount_cents: int,
) -> None:
    """`payment.penalty_captured` — late_cancel / no_show / weak_conflict."""
    emit_payment_penalty_captured(reservation, penalty_kind, amount_cents)
    logger.info(
        "notify.penalty_captured user=%s reservation=%s kind=%s amount=%d",
        user.id,
        reservation.id,
        penalty_kind.value,
        amount_cents,
    )


# ---------------------------------------------------------------------------
# Generic structured-log entry point used by tests / future drivers
# ---------------------------------------------------------------------------


def log_notification(kind: str, payload: dict[str, Any]) -> None:
    logger.info("notify kind=%s payload=%s", kind, payload)
