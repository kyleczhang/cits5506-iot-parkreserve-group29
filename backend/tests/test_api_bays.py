"""Bay API tests for public status reads and admin event-history access."""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote
from uuid import uuid4

from app.extensions import db
from app.models import BayEventKind, BayState, ParkingBay
from app.services import event_service
from app.utils.time import utcnow


def test_list_returns_all_three_bays_after_seed(client, bays):
    resp = client.get("/api/v1/bays")
    assert resp.status_code == 200
    body = resp.get_json()
    assert {b["code"] for b in body} == {"A1", "A2", "A3"}
    assert {b["state"] for b in body} == {"available"}


def test_get_bay_detail(client, bays):
    resp = client.get("/api/v1/bays/A1")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["code"] == "A1"
    assert body["state"] == "available"
    assert body["current_reservation_id"] is None


def test_get_unknown_bay_is_404(client, bays):
    resp = client.get("/api/v1/bays/Z9")
    assert resp.status_code == 404


def _seed_bay_events(app, bay_code: str, count: int = 3) -> None:
    """Insert ``count`` audit rows on ``bay_code`` via the real writer."""
    with app.app_context():
        bay = db.session.execute(
            db.select(ParkingBay).where(ParkingBay.code == bay_code)
        ).scalar_one()
        for _ in range(count):
            event_service.record(
                bay_id=bay.id,
                kind=BayEventKind.STATE_CHANGED,
                from_state=BayState.AVAILABLE,
                to_state=BayState.RESERVED,
                source_event_id=uuid4(),
                payload={"distance_cm": 12.5},
            )
        db.session.commit()


def test_admin_can_list_bay_events_newest_first(app, client, bays, admin_headers):
    _seed_bay_events(app, "A1", count=3)

    resp = client.get("/api/v1/bays/A1/events", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 3
    timestamps = [row["created_at"] for row in body]
    assert timestamps == sorted(timestamps, reverse=True)
    assert all(row["kind"] == "state_changed" for row in body)
    assert all(row["from_state"] == "available" for row in body)
    assert all(row["to_state"] == "reserved" for row in body)


def test_bay_events_unauthenticated_is_401(client, bays):
    resp = client.get("/api/v1/bays/A1/events")
    assert resp.status_code == 401


def test_bay_events_non_admin_is_403(client, bays, auth_headers):
    resp = client.get("/api/v1/bays/A1/events", headers=auth_headers)
    assert resp.status_code == 403


def test_bay_events_unknown_bay_is_404(client, bays, admin_headers):
    resp = client.get("/api/v1/bays/Z9/events", headers=admin_headers)
    assert resp.status_code == 404


def test_bay_events_limit_clamped_and_respected(app, client, bays, admin_headers):
    _seed_bay_events(app, "A1", count=5)

    resp = client.get("/api/v1/bays/A1/events?limit=2", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


def test_bay_events_before_cursor_filters(app, client, bays, admin_headers):
    _seed_bay_events(app, "A1", count=3)
    cutoff = quote((utcnow() - timedelta(days=1)).isoformat())

    resp = client.get(f"/api/v1/bays/A1/events?before={cutoff}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_bay_events_invalid_before_is_422(client, bays, admin_headers):
    resp = client.get("/api/v1/bays/A1/events?before=not-a-date", headers=admin_headers)
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "invalid_query_param"
