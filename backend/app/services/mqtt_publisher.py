"""Centralised MQTT outbound publisher used by every service.

All ``cloud/bay/<code>/reservation`` payloads must include the reserving
user's *current* bound-plate list so the Pi's LPR matcher always has the
freshest set. Any currently bound plate counts as a match.
This module is the single source of that contract.

If MQTT is disabled (tests / dev) the call is a no-op — the existence of the
publish is recorded by callers via ``bay_events`` so test assertions still
work without a broker.
"""

from __future__ import annotations

import logging

from flask import current_app

from app.models import Reservation, User
from app.mqtt import get_publisher
from app.mqtt.topics import (
    ReservationActionLiteral,
    ReservationCommand,
    ReservationReleaseReason,
)
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def publish_reservation_command(
    *,
    bay_code: str,
    action: ReservationActionLiteral,
    reservation: Reservation | None,
    user: User | None,
    bound_plates: list[str],
    reason: ReservationReleaseReason | None = None,
) -> None:
    """Publish to ``cloud/bay/<code>/reservation`` with the bound-plate list.

    A None ``reservation`` is allowed for synthetic events; in practice every
    business call has one.
    """
    payload = ReservationCommand(
        action=action,
        reservation_id=reservation.id if reservation is not None else None,
        user_id=user.id if user is not None else None,
        bound_plates=list(bound_plates),
        expected_arrival_time=(
            reservation.expected_arrival_time if reservation is not None else None
        ),
        reason=reason,
        ts=utcnow(),
    ).model_dump(mode="json")

    publisher = get_publisher(current_app._get_current_object())
    if publisher is None:
        logger.debug(
            "mqtt.command_skipped_disabled bay=%s action=%s",
            bay_code,
            action,
        )
        return
    publisher.publish_reservation(bay_code, payload)
