"""Timezone-aware time helpers used by services, jobs, and tests."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(UTC)
