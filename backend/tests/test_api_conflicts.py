"""Admin conflict view + Pi → backend evidence-image upload."""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from uuid import uuid4

from app.extensions import db
from app.models import (
    Conflict,
    ConflictKind,
    ParkingBay,
    Reservation,
    ReservationStatus,
)
from app.mqtt.topics import PiInboundEventPayload
from app.services.event_dispatcher import dispatch_event
from app.utils.time import utcnow


def _make_active_reservation(session, *, bay_code: str, user) -> Reservation:
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == bay_code)).scalar_one()
    res = Reservation(
        bay_id=bay.id,
        user_id=user.id,
        status=ReservationStatus.ACTIVE,
        expected_arrival_time=utcnow() + timedelta(minutes=10),
    )
    session.add(res)
    session.commit()
    return res


def test_admin_can_list_open_conflicts(
    app,
    session,
    bays,
    admin,
    admin_headers,
    user_with_plates,
    client,
):
    _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    payload = PiInboundEventPayload(
        event="conflict_strong",
        ts=utcnow(),
        event_id=uuid4(),
        recognised_plate="ZZZ999",
        lpr_confidence=0.91,
    )
    with app.app_context():
        dispatch_event(bay_code="A1", payload=payload)

    resp = client.get("/api/v1/conflicts", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["kind"] == "strong"
    assert body[0]["recognised_plate"] == "ZZZ999"


def test_non_admin_cannot_list_conflicts(client, auth_headers, bays):
    resp = client.get("/api/v1/conflicts", headers=auth_headers)
    assert resp.status_code == 403


def test_pi_evidence_upload_persists_url_and_purge_at(
    app,
    session,
    bays,
    user_with_plates,
    client,
):
    _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    event_id = uuid4()

    # Pi MQTT event + image upload (evidence first; MQTT second)
    resp = client.post(
        "/api/v1/internal/conflicts/evidence",
        data={
            "bay_code": "A1",
            "source_event_id": str(event_id),
            "recognised_plate": "ZZZ999",
            "image": (BytesIO(b"\xff\xd8\xff fake-jpeg"), "evidence.jpg"),
        },
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer test-evidence-token"},
    )
    assert resp.status_code == 201, resp.get_json()

    payload = PiInboundEventPayload(
        event="conflict_strong",
        ts=utcnow(),
        event_id=event_id,
        recognised_plate="ZZZ999",
        lpr_confidence=0.91,
    )
    with app.app_context():
        dispatch_event(bay_code="A1", payload=payload)

        conflicts = db.session.execute(db.select(Conflict)).scalars().all()
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c.kind == ConflictKind.STRONG
        assert c.evidence_image_url is not None
        assert c.image_purge_at is not None


def test_evidence_upload_rejects_missing_token(client, bays):
    resp = client.post(
        "/api/v1/internal/conflicts/evidence",
        data={"bay_code": "A1", "source_event_id": str(uuid4()), "recognised_plate": "Z9"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 401
