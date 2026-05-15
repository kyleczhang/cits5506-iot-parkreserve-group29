"""Read models returned by bay and bay-event API endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class BayOut(BaseModel):
    code: str
    label: str
    state: str
    mirror_state: str
    last_distance_cm: Decimal | None
    sensor_last_seen_at: datetime | None
    current_reservation_id: str | None
    current_reservation_arrival: datetime | None
    check_in_grace_expires_at: datetime | None


class BayEventOut(BaseModel):
    id: int
    kind: str
    from_state: str | None
    to_state: str | None
    reservation_id: str | None
    payload: dict[str, Any]
    created_at: datetime
