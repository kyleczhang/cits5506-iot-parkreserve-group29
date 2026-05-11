"""Request and response schemas for user-bound licence plates."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PlateAddRequest(BaseModel):
    plate: str = Field(min_length=1, max_length=16)
    label: str | None = Field(default=None, max_length=64)


class PlateOut(BaseModel):
    id: str
    plate: str
    label: str | None
    created_at: datetime
