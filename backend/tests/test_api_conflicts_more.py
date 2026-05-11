"""Additional admin-conflict API coverage: resolve flow, evidence GET, edge cases."""

from __future__ import annotations

import os
from datetime import timedelta
from uuid import uuid4

from app.extensions import db
from app.models import (
    Conflict,
    ConflictKind,
    ParkingBay,
    Reservation,
    ReservationStatus,
)
from app.utils.time import utcnow


def _seed_strong_with_image(session, _evidence_dir, *, bay_code="A1", user, app):
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == bay_code)).scalar_one()
    booked = utcnow() - timedelta(minutes=20)
    res = Reservation(
        bay_id=bay.id,
        user_id=user.id,
        status=ReservationStatus.ACTIVE,
        booked_at=booked,
        expected_arrival_time=booked + timedelta(minutes=15),
    )
    session.add(res)
    session.commit()

    eid = uuid4()
    image_path = os.path.join(_evidence_dir, f"{eid}.jpg")
    with open(image_path, "wb") as fh:
        fh.write(b"\xff\xd8\xff fake")
    purge_at = utcnow() + timedelta(days=10)
    c = Conflict(
        bay_id=bay.id,
        reservation_id=res.id,
        kind=ConflictKind.STRONG,
        recognised_plate="ZZZ999",
        source_event_id=eid,
        evidence_image_url=image_path,
        image_purge_at=purge_at,
    )
    session.add(c)
    session.commit()
    return c


def test_admin_can_get_evidence_image(
    app,
    session,
    bays,
    admin,
    admin_headers,
    user_with_plates,
    _evidence_dir,
    client,
):
    c = _seed_strong_with_image(session, _evidence_dir, user=user_with_plates, app=app)
    resp = client.get(f"/api/v1/conflicts/{c.id}/evidence", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"


def test_admin_evidence_404_after_purge(
    app,
    session,
    bays,
    admin,
    admin_headers,
    user_with_plates,
    _evidence_dir,
    client,
):
    c = _seed_strong_with_image(session, _evidence_dir, user=user_with_plates, app=app)
    # Purge the image (simulate retention expiry)
    os.remove(c.evidence_image_url)
    with app.app_context():
        c2 = db.session.get(Conflict, c.id)
        c2.evidence_image_url = None
        c2.image_purge_at = None
        db.session.commit()
    resp = client.get(f"/api/v1/conflicts/{c.id}/evidence", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "evidence_purged"


def test_admin_can_resolve_weak_conflict(
    app,
    session,
    bays,
    admin,
    admin_headers,
    user_with_plates,
    client,
):
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    c = Conflict(
        bay_id=bay.id,
        kind=ConflictKind.WEAK,
        source_event_id=uuid4(),
    )
    session.add(c)
    session.commit()

    resp = client.post(
        f"/api/v1/conflicts/{c.id}/resolve",
        json={"resolution": "vehicle_left"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["resolved_at"] is not None
    assert body["resolution"] == "vehicle_left"


def test_admin_cannot_resolve_strong_with_user_check_in(
    app,
    session,
    bays,
    admin,
    admin_headers,
    user_with_plates,
    client,
):
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    c = Conflict(
        bay_id=bay.id,
        kind=ConflictKind.STRONG,
        recognised_plate="ZZZ999",
        source_event_id=uuid4(),
    )
    session.add(c)
    session.commit()

    resp = client.post(
        f"/api/v1/conflicts/{c.id}/resolve",
        json={"resolution": "user_arrived_and_checked_in"},
        headers=admin_headers,
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "strong_conflict_user_resolution_invalid"


def test_evidence_upload_requires_image_part(client, bays):
    resp = client.post(
        "/api/v1/internal/conflicts/evidence",
        data={
            "bay_code": "A1",
            "source_event_id": str(uuid4()),
            "recognised_plate": "ZZ9",
        },
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer test-evidence-token"},
    )
    assert resp.status_code == 422


def test_admin_resolve_unknown_conflict_404(client, admin_headers):
    resp = client.post(
        f"/api/v1/conflicts/{uuid4()}/resolve",
        json={"resolution": "vehicle_left"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
