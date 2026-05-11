"""Audit-log writer for `bay_events` rows.

Every state-changing path (MQTT ingest + REST writes) inserts exactly one
row here. ``source_event_id`` (Pi-supplied UUID) gives us idempotent replay:
a duplicate insert is silently dropped via ``ON CONFLICT DO NOTHING`` so
breaches are never double-counted on reconnect.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.extensions import db
from app.models import BayEvent, BayEventKind, BayState


def record(
    *,
    bay_id: int,
    kind: BayEventKind,
    from_state: BayState | None = None,
    to_state: BayState | None = None,
    reservation_id: UUID | None = None,
    source_event_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> BayEvent | None:
    """Insert a bay_events row, idempotent on ``source_event_id``.

    Returns the inserted row, or None if the insert was a duplicate (replay).
    Backend-originated events (no ``source_event_id``) always insert.
    """
    if source_event_id is not None:
        stmt = (
            pg_insert(BayEvent)
            .values(
                bay_id=bay_id,
                kind=kind,
                from_state=from_state,
                to_state=to_state,
                reservation_id=reservation_id,
                source_event_id=source_event_id,
                payload=payload or {},
            )
            .on_conflict_do_nothing(index_elements=["source_event_id"])
            .returning(BayEvent.id)
        )
        result = db.session.execute(stmt).first()
        if result is None:
            return None
        return db.session.execute(select(BayEvent).where(BayEvent.id == result.id)).scalar_one()

    event = BayEvent(
        bay_id=bay_id,
        kind=kind,
        from_state=from_state,
        to_state=to_state,
        reservation_id=reservation_id,
        payload=payload or {},
    )
    db.session.add(event)
    db.session.flush()
    return event


def already_processed(source_event_id: UUID) -> bool:
    """Cheap pre-check used by handlers that want to short-circuit before
    doing any other work. The unique constraint on ``source_event_id`` is the
    real authority — but checking first lets us skip enqueuing notifications,
    publishing MQTT, etc."""
    return (
        db.session.execute(
            select(BayEvent.id).where(BayEvent.source_event_id == source_event_id)
        ).first()
        is not None
    )
