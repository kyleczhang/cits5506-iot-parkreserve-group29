"""Read-only access to the ``bay_events`` audit log.

Writes go through :mod:`app.services.event_service`. This module exists for
the admin audit-log view at ``GET /api/v1/bays/{code}/events``.
Queries are served by the ``bay_events_bay_time_idx`` index on
``(bay_id, created_at)``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.extensions import db
from app.models import BayEvent, ParkingBay
from app.utils.errors import NotFoundError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def list_for_bay(
    code: str,
    *,
    limit: int = DEFAULT_LIMIT,
    before: datetime | None = None,
) -> list[BayEvent]:
    """Return audit-log rows for one bay, newest first.

    ``before`` acts as a keyset cursor — pass the previous page's last
    ``created_at`` to fetch the next page. ``limit`` is clamped to
    ``[1, MAX_LIMIT]``.
    """
    bay = db.session.execute(select(ParkingBay).where(ParkingBay.code == code)).scalar_one_or_none()
    if bay is None:
        raise NotFoundError(f"bay {code!r} does not exist", code="bay_not_found")

    limit = max(1, min(limit, MAX_LIMIT))

    stmt = (
        select(BayEvent)
        .where(BayEvent.bay_id == bay.id)
        .order_by(BayEvent.created_at.desc(), BayEvent.id.desc())
        .limit(limit)
    )
    if before is not None:
        stmt = stmt.where(BayEvent.created_at < before)
    return list(db.session.execute(stmt).scalars())
