"""Reservation API payload schemas for booking and check-in flows."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.payment import CardDetails


class ReservationCreateRequest(BaseModel):
    bay_code: str = Field(min_length=1, max_length=16)
    expected_arrival_time: datetime
    card: CardDetails


class ReservationCheckInRequest(BaseModel):
    bay_code: str = Field(min_length=1, max_length=16)
    source: Literal["qr", "manual"]


class ReservationDepositInfo(BaseModel):
    deposit_cents: int


class ReservationOut(BaseModel):
    id: str
    bay_code: str
    user_id: str
    status: str
    expected_arrival_time: datetime
    booked_at: datetime
    check_in_grace_expires_at: datetime | None
    checked_in_at: datetime | None
    check_in_mechanism: str | None
    cancelled_at: datetime | None
    completed_at: datetime | None
    payment: ReservationDepositInfo | None = None
