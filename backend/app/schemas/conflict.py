"""Admin conflict API payload schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class ConflictOut(BaseModel):
    id: str
    bay_code: str
    kind: str
    reservation_id: str | None
    recognised_plate: str | None
    lpr_confidence: Decimal | None
    evidence_image_url: str | None
    image_purge_at: datetime | None
    detected_at: datetime
    resolved_at: datetime | None
    resolution: str | None


class ConflictResolveRequest(BaseModel):
    resolution: Literal["vehicle_left", "admin_resolved", "user_arrived_and_checked_in"]
