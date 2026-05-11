"""Cover the lightweight on_state / on_event / on_heartbeat handlers
registered by `register_default_handlers`. We feed them dict payloads and
verify they parse, dispatch, and reject malformed input gracefully.
"""

from __future__ import annotations

from uuid import uuid4

from app.extensions import db
from app.models import BayState, ParkingBay
from app.mqtt.handlers import register_default_handlers
from app.utils.time import utcnow


class _StubClient:
    def __init__(self):
        self.state_handler = None
        self.event_handler = None
        self.heartbeat_handler = None

    def on_state(self, h):
        self.state_handler = h

    def on_event(self, h):
        self.event_handler = h

    def on_heartbeat(self, h):
        self.heartbeat_handler = h


def test_register_routes_state_event_through_to_apply_state(app, session, bays):
    stub = _StubClient()
    register_default_handlers(app, stub)

    payload = {
        "state": "occupied",
        "last_distance_cm": 4.5,
        "ts": utcnow().isoformat(),
        "event_id": str(uuid4()),
    }
    stub.state_handler("state", "A1", payload)

    with app.app_context():
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.OCCUPIED


def test_register_drops_invalid_state_payload(app, session, bays):
    stub = _StubClient()
    register_default_handlers(app, stub)

    # Missing required `state` field
    stub.state_handler("state", "A1", {"last_distance_cm": 4.5, "ts": utcnow().isoformat()})

    # Bay state stays AVAILABLE (the payload was dropped)
    with app.app_context():
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.AVAILABLE


def test_register_drops_invalid_event_payload(app, session, bays):
    stub = _StubClient()
    register_default_handlers(app, stub)

    stub.event_handler("event", "A1", {"event": "definitely-not-real", "ts": utcnow().isoformat()})


def test_pi_cannot_send_conflict_weak(app, session, bays):
    stub = _StubClient()
    register_default_handlers(app, stub)

    stub.event_handler(
        "event",
        "A1",
        {"event": "conflict_weak", "ts": utcnow().isoformat(), "event_id": str(uuid4())},
    )

    with app.app_context():
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.AVAILABLE


def test_heartbeat_handler_just_logs(app, session, bays):
    stub = _StubClient()
    register_default_handlers(app, stub)

    # Should not raise
    stub.heartbeat_handler("heartbeat", "", {"pi_id": "pi-01", "ts": utcnow().isoformat()})
