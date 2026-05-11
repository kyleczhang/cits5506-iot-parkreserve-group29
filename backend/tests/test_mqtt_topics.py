"""Topic-helper unit tests — pure functions, no broker required."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from app.mqtt.topics import (
    ReservationCommand,
    event_topic,
    heartbeat_topic,
    parse_event_topic,
    parse_reservation_topic,
    parse_state_topic,
    reservation_topic,
    resync_topic,
    state_topic,
)


def test_state_round_trip():
    assert state_topic("cloud", "A1") == "cloud/bay/A1/state"
    assert parse_state_topic("cloud/bay/A1/state") == "A1"
    assert parse_state_topic("cloud/bay/A1/event") is None


def test_event_round_trip():
    assert event_topic("cloud", "A1") == "cloud/bay/A1/event"
    assert parse_event_topic("cloud/bay/A1/event") == "A1"
    assert parse_event_topic("not/a/match") is None


def test_reservation_round_trip():
    assert reservation_topic("cloud", "A1") == "cloud/bay/A1/reservation"
    assert parse_reservation_topic("cloud/bay/A1/reservation") == "A1"


def test_system_topics():
    assert heartbeat_topic("cloud") == "cloud/system/heartbeat"
    assert resync_topic("cloud") == "cloud/system/resync"


def test_release_command_requires_reason():
    with pytest.raises(ValueError):
        ReservationCommand(
            action="release",
            reservation_id=uuid4(),
            user_id=uuid4(),
            bound_plates=[],
            ts=datetime.now(),
        )


def test_non_release_command_rejects_reason():
    with pytest.raises(ValueError):
        ReservationCommand(
            action="create",
            reservation_id=uuid4(),
            user_id=uuid4(),
            bound_plates=["ABC123"],
            reason="completed",
            ts=datetime.now(),
        )
