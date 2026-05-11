"""MQTT-side tests: backend ingests Pi-published `cloud/bay/<code>/state` and
`cloud/bay/<code>/event` payloads. We invoke the service-layer functions
directly with synthetic payloads — no broker required.
"""

from __future__ import annotations

from uuid import uuid4

from app.extensions import db
from app.models import BayEvent, BayEventKind, BayState, ParkingBay, SensorReading
from app.mqtt.topics import StatePayload
from app.services.bay_service import apply_state
from app.utils.time import utcnow


def test_state_update_persisted_and_event_recorded(app, session, bays):
    payload = StatePayload(
        state="occupied",
        last_distance_cm=4.5,
        ts=utcnow(),
        event_id=uuid4(),
    )
    with app.app_context():
        apply_state(bay_code="A1", payload=payload)

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.OCCUPIED
        assert float(bay.last_distance_cm) == 4.5

        readings = db.session.execute(db.select(SensorReading)).scalars().all()
        assert len(readings) == 1
        assert readings[0].occupied is True

        events = (
            db.session.execute(
                db.select(BayEvent).where(BayEvent.kind == BayEventKind.STATE_CHANGED)
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert events[0].from_state == BayState.AVAILABLE
        assert events[0].to_state == BayState.OCCUPIED


def test_state_update_unknown_bay_is_dropped_silently(app, session, bays):
    payload = StatePayload(
        state="occupied",
        last_distance_cm=4.5,
        ts=utcnow(),
        event_id=uuid4(),
    )
    with app.app_context():
        # Should not raise; should not insert any rows.
        apply_state(bay_code="ZZ", payload=payload)

        readings = db.session.execute(db.select(SensorReading)).scalars().all()
        assert readings == []


def test_state_update_replay_is_idempotent(app, session, bays):
    eid = uuid4()
    payload = StatePayload(
        state="occupied",
        last_distance_cm=4.5,
        ts=utcnow(),
        event_id=eid,
    )
    with app.app_context():
        apply_state(bay_code="A1", payload=payload)
        apply_state(bay_code="A1", payload=payload)

        events = (
            db.session.execute(
                db.select(BayEvent).where(BayEvent.kind == BayEventKind.STATE_CHANGED)
            )
            .scalars()
            .all()
        )
        # Replay event_id deduplicated in event_service.record
        assert len(events) == 1
