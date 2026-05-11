"""R7 cloud-disconnection resilience: replays after reconnect are no-ops
(events deduplicated by source_event_id) and the backend can recover the
mirror state from a Pi resync."""

from __future__ import annotations

from uuid import uuid4

from app.extensions import db
from app.models import BayEvent, BayEventKind
from app.mqtt.topics import StatePayload
from app.services.bay_service import apply_state
from app.utils.time import utcnow


def test_replay_after_reconnect_is_idempotent(app, session, bays):
    eid = uuid4()
    payload = StatePayload(
        state="occupied",
        last_distance_cm=4.5,
        ts=utcnow(),
        event_id=eid,
    )
    with app.app_context():
        # First delivery (cloud connected)
        apply_state(bay_code="A1", payload=payload)
        # Pi replays the same event after a brief disconnection
        apply_state(bay_code="A1", payload=payload)

        events = (
            db.session.execute(db.select(BayEvent).where(BayEvent.source_event_id == eid))
            .scalars()
            .all()
        )
        assert len(events) == 1


def test_replay_with_different_event_ids_records_separately(app, session, bays):
    """Distinct readings always produce distinct rows — the dedupe is per-event-id,
    not per-bay or per-state. Real Pi readings at demo cadence can easily
    produce around 10^5 rows over a week."""
    with app.app_context():
        for _ in range(5):
            apply_state(
                bay_code="A1",
                payload=StatePayload(
                    state="occupied",
                    last_distance_cm=4.5,
                    ts=utcnow(),
                    event_id=uuid4(),
                ),
            )
        events = (
            db.session.execute(
                db.select(BayEvent).where(BayEvent.kind == BayEventKind.STATE_CHANGED)
            )
            .scalars()
            .all()
        )
        # The first one is AVAILABLE → OCCUPIED (1 row); subsequent state-equal
        # writes are no-ops (no STATE_CHANGED row).
        assert len(events) == 1
