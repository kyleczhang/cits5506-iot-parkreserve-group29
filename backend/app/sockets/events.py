"""Server → client WebSocket emissions on the ``/ws`` namespace.

Events emitted:

- ``bay.updated``                       (state mirror updates)
- ``reservation.updated``               (any status transition)
- ``reservation.pending_check_in``      ("vehicle detected — please check in")
- ``reservation.auto_checked_in``       ("you're checked in at Bay X")
- ``plate.updated``                     (user's bound list changed)
- ``conflict.raised`` / ``conflict.resolved``
"""

from __future__ import annotations

import logging
from typing import Any

from app.extensions import socketio
from app.models import Conflict, LicencePlate, ParkingBay, PenaltyKind, Reservation, User

logger = logging.getLogger(__name__)

NAMESPACE = "/ws"


# ---------------------------------------------------------------------------
# Bay
# ---------------------------------------------------------------------------


def emit_bay_updated(bay: ParkingBay) -> None:
    socketio.emit("bay.updated", _bay_payload(bay), namespace=NAMESPACE)


def _bay_payload(bay: ParkingBay) -> dict[str, Any]:
    return {
        "code": bay.code,
        "label": bay.label,
        "state": bay.public_state().value,
        "mirror_state": bay.state.value,
        "last_distance_cm": (
            float(bay.last_distance_cm) if bay.last_distance_cm is not None else None
        ),
        "sensor_last_seen_at": _iso_or_none(bay.sensor_last_seen_at),
        "current_reservation_id": (
            str(bay.current_reservation_id) if bay.current_reservation_id else None
        ),
        "updated_at": _iso_or_none(bay.updated_at),
    }


# ---------------------------------------------------------------------------
# Reservation
# ---------------------------------------------------------------------------


def emit_reservation_updated(reservation: Reservation, bay: ParkingBay) -> None:
    socketio.emit(
        "reservation.updated",
        _reservation_payload(reservation, bay),
        namespace=NAMESPACE,
    )


def emit_reservation_auto_checked_in(
    reservation: Reservation, bay: ParkingBay, recognised_plate: str
) -> None:
    socketio.emit(
        "reservation.auto_checked_in",
        {
            **_reservation_payload(reservation, bay),
            "recognised_plate": recognised_plate,
            "checked_in_at": _iso_or_none(reservation.checked_in_at),
        },
        namespace=NAMESPACE,
    )


def emit_reservation_pending_check_in(reservation: Reservation, bay: ParkingBay) -> None:
    socketio.emit(
        "reservation.pending_check_in",
        {
            "id": str(reservation.id),
            "bay_code": bay.code,
            "user_id": str(reservation.user_id),
            "detected_at": _iso_or_none(reservation.updated_at),
            "check_in_grace_expires_at": _iso_or_none(reservation.check_in_grace_expires_at),
        },
        namespace=NAMESPACE,
    )


def _reservation_payload(reservation: Reservation, bay: ParkingBay) -> dict[str, Any]:
    return {
        "id": str(reservation.id),
        "bay_code": bay.code,
        "user_id": str(reservation.user_id),
        "status": reservation.status.value,
        "expected_arrival_time": _iso_or_none(reservation.expected_arrival_time),
        "booked_at": _iso_or_none(reservation.booked_at),
        "check_in_grace_expires_at": _iso_or_none(reservation.check_in_grace_expires_at),
        "checked_in_at": _iso_or_none(reservation.checked_in_at),
        "check_in_mechanism": (
            reservation.check_in_mechanism.value
            if reservation.check_in_mechanism is not None
            else None
        ),
        "cancelled_at": _iso_or_none(reservation.cancelled_at),
        "completed_at": _iso_or_none(reservation.completed_at),
    }


# ---------------------------------------------------------------------------
# Plates
# ---------------------------------------------------------------------------


def emit_plate_updated(user: User, plates: list[LicencePlate]) -> None:
    socketio.emit(
        "plate.updated",
        {
            "user_id": str(user.id),
            "plates": [{"plate": p.plate, "label": p.label} for p in plates],
        },
        namespace=NAMESPACE,
    )


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------


def emit_conflict(bay: ParkingBay, conflict: Conflict, *, raised: bool) -> None:
    event = "conflict.raised" if raised else "conflict.resolved"
    socketio.emit(
        event,
        {
            "id": str(conflict.id),
            "bay_code": bay.code,
            "kind": conflict.kind.value,
            "recognised_plate": conflict.recognised_plate,
            "detected_at": _iso_or_none(conflict.detected_at),
            "resolved_at": _iso_or_none(conflict.resolved_at),
            "resolution": (conflict.resolution.value if conflict.resolution is not None else None),
        },
        namespace=NAMESPACE,
    )


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


def emit_payment_deposit_released(reservation: Reservation, amount_cents: int, reason: str) -> None:
    socketio.emit(
        "payment.deposit_released",
        {
            "reservation_id": str(reservation.id),
            "user_id": str(reservation.user_id),
            "amount_cents": amount_cents,
            "reason": reason,
        },
        namespace=NAMESPACE,
    )


def emit_payment_refunded(reservation: Reservation, amount_cents: int) -> None:
    socketio.emit(
        "payment.refunded",
        {
            "reservation_id": str(reservation.id),
            "user_id": str(reservation.user_id),
            "amount_cents": amount_cents,
            "reason": "strong_conflict",
        },
        namespace=NAMESPACE,
    )


def emit_payment_penalty_captured(
    reservation: Reservation, penalty_kind: PenaltyKind, amount_cents: int
) -> None:
    socketio.emit(
        "payment.penalty_captured",
        {
            "reservation_id": str(reservation.id),
            "user_id": str(reservation.user_id),
            "penalty_kind": penalty_kind.value,
            "amount_cents": amount_cents,
        },
        namespace=NAMESPACE,
    )


def _iso_or_none(dt) -> str | None:
    return dt.isoformat() if dt else None


@socketio.on("connect", namespace=NAMESPACE)
def _on_connect():
    logger.debug("socket.connect")


@socketio.on("disconnect", namespace=NAMESPACE)
def _on_disconnect():
    logger.debug("socket.disconnect")
