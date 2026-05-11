"""Payment API payload schemas for transaction history responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CardDetails(BaseModel):
    """Card sub-object for booking.

    Validated against `mock_cards` in-process. Never reaches a real bank.
    """

    number: str = Field(min_length=13, max_length=19, pattern=r"^[0-9]+$")
    cvv: str = Field(min_length=3, max_length=4, pattern=r"^[0-9]+$")
    expiry_month: int = Field(ge=1, le=12)
    expiry_year: int = Field(ge=2024, le=2099)
    holder_name: str = Field(min_length=1, max_length=120)


class TransactionOut(BaseModel):
    id: str
    reservation_id: str
    action: Literal["pre_auth", "release", "refund", "penalty_capture"]
    penalty_kind: Literal["late_cancel", "no_show", "weak_conflict"] | None
    amount_cents: int
    status: Literal["succeeded", "failed", "voided"]
    occurred_at: datetime


class TransactionListResponse(BaseModel):
    transactions: list[TransactionOut]
