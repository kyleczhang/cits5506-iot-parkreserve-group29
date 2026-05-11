"""MQTT topic helpers and pydantic payload schemas.

Topology:

* Pi → backend
    - ``cloud/bay/<code>/state``  bay-state mirror updates
    - ``cloud/bay/<code>/event``  Pi-originated state-machine events
      (auto_check_in, pending_check_in, conflict_strong,
      check_in_confirmed, sensor_online, sensor_offline)
    - ``cloud/system/heartbeat``  every ~10s

* Backend → Pi
    - ``cloud/bay/<code>/reservation``  reservation lifecycle commands
      (create/cancel/check_in/release/expire_check_in) and plate-list
      updates (action="update_plates")
    - ``cloud/system/resync``  empty payload, request bay state replay
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Topic builders / parsers
# ---------------------------------------------------------------------------


def state_topic(prefix: str, bay_code: str) -> str:
    return f"{prefix}/bay/{bay_code}/state"


def event_topic(prefix: str, bay_code: str) -> str:
    return f"{prefix}/bay/{bay_code}/event"


def reservation_topic(prefix: str, bay_code: str) -> str:
    return f"{prefix}/bay/{bay_code}/reservation"


def heartbeat_topic(prefix: str) -> str:
    return f"{prefix}/system/heartbeat"


def resync_topic(prefix: str) -> str:
    return f"{prefix}/system/resync"


_state_re = re.compile(r"^(?P<prefix>[^/]+)/bay/(?P<code>[^/]+)/state$")
_event_re = re.compile(r"^(?P<prefix>[^/]+)/bay/(?P<code>[^/]+)/event$")
_reservation_re = re.compile(r"^(?P<prefix>[^/]+)/bay/(?P<code>[^/]+)/reservation$")


def parse_state_topic(topic: str) -> str | None:
    m = _state_re.match(topic)
    return m.group("code") if m else None


def parse_event_topic(topic: str) -> str | None:
    m = _event_re.match(topic)
    return m.group("code") if m else None


def parse_reservation_topic(topic: str) -> str | None:
    m = _reservation_re.match(topic)
    return m.group("code") if m else None


# ---------------------------------------------------------------------------
# Payload schemas
# ---------------------------------------------------------------------------

BayStateLiteral = Literal[
    "available",
    "reserved",
    "occupied",
    "pending_check_in",
    "reserved_checked_in",
    "conflict",
    "offline",
]

EventLiteral = Literal[
    "sensor_online",
    "sensor_offline",
    "auto_check_in",
    "pending_check_in",
    "check_in_confirmed",
    "conflict_strong",
    "conflict_weak",
    "no_show",
]

ReservationActionLiteral = Literal[
    "create",
    "cancel",
    "check_in",
    "update_plates",
    "release",
    "expire_check_in",
]
ReservationReleaseReason = Literal["no_show", "completed", "abandoned", "admin_override"]


class StatePayload(BaseModel):
    """``cloud/bay/<code>/state`` — Pi reports bay state + last sensor reading."""

    model_config = ConfigDict(extra="forbid")

    state: BayStateLiteral
    last_distance_cm: float = Field(ge=0, le=500)
    ts: datetime
    event_id: UUID | None = None


class _BaseEventPayload(BaseModel):
    """Common event fields shared by Pi-originated and internal events."""

    model_config = ConfigDict(extra="forbid")

    ts: datetime
    event_id: UUID | None = None
    reservation_id: UUID | None = None
    recognised_plate: str | None = Field(default=None, max_length=16)
    lpr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PiInboundEventPayload(_BaseEventPayload):
    """``cloud/bay/<code>/event`` — events that the Pi is allowed to publish."""

    event: Literal[
        "sensor_online",
        "sensor_offline",
        "auto_check_in",
        "pending_check_in",
        "check_in_confirmed",
        "conflict_strong",
    ]


class InternalEventPayload(_BaseEventPayload):
    """Synthesised backend-side reservation events dispatched internally."""

    event: Literal["conflict_weak", "no_show"]


EventPayload: TypeAlias = PiInboundEventPayload | InternalEventPayload


class ReservationCommand(BaseModel):
    """``cloud/bay/<code>/reservation`` — backend → Pi.

    The ``bound_plates`` list is included on every payload so the Pi's LPR
    matcher always has the freshest set. Any currently bound plate counts as
    a match.
    """

    model_config = ConfigDict(extra="forbid")

    action: ReservationActionLiteral
    reservation_id: UUID | None = None
    user_id: UUID | None = None
    bound_plates: list[str] = Field(default_factory=list)
    expected_arrival_time: datetime | None = None
    reason: ReservationReleaseReason | None = None
    ts: datetime

    @model_validator(mode="after")
    def validate_reason(self) -> ReservationCommand:
        if self.action == "release" and self.reason is None:
            raise ValueError("reason is required when action='release'")
        if self.action != "release" and self.reason is not None:
            raise ValueError("reason is only allowed when action='release'")
        return self


class HeartbeatPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pi_id: str | None = None
    ts: datetime | None = None


def _decimal(v: float | Decimal) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))
