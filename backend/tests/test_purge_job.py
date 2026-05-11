"""30-day evidence-image purge job."""

from __future__ import annotations

import os
from datetime import timedelta
from uuid import uuid4

from app.extensions import db
from app.models import Conflict, ConflictKind, ParkingBay
from app.services.conflict_service import purge_expired_evidence
from app.utils.time import utcnow


def test_purge_clears_url_and_object_when_expired(app, session, bays, _evidence_dir):
    a1, a2 = (
        session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one(),
        session.execute(db.select(ParkingBay).where(ParkingBay.code == "A2")).scalar_one(),
    )
    image_path = os.path.join(_evidence_dir, "expired.jpg")
    with open(image_path, "wb") as fh:
        fh.write(b"\xff\xd8\xff fake")

    expired_purge = utcnow() - timedelta(days=1)
    fresh_purge = utcnow() + timedelta(days=10)

    expired_row = Conflict(
        bay_id=a1.id,
        kind=ConflictKind.STRONG,
        recognised_plate="EXPIRED1",
        source_event_id=uuid4(),
        evidence_image_url=image_path,
        image_purge_at=expired_purge,
    )
    fresh_path = os.path.join(_evidence_dir, "fresh.jpg")
    with open(fresh_path, "wb") as fh:
        fh.write(b"\xff\xd8\xff fresh")
    fresh_row = Conflict(
        bay_id=a2.id,
        kind=ConflictKind.STRONG,
        recognised_plate="FRESH1",
        source_event_id=uuid4(),
        evidence_image_url=fresh_path,
        image_purge_at=fresh_purge,
    )
    session.add_all([expired_row, fresh_row])
    session.commit()

    with app.app_context():
        purged = purge_expired_evidence()

    assert len(purged) == 1
    assert not os.path.exists(image_path)
    assert os.path.exists(fresh_path)

    with app.app_context():
        rows = {c.recognised_plate: c for c in db.session.execute(db.select(Conflict)).scalars()}
        assert rows["EXPIRED1"].evidence_image_url is None
        assert rows["EXPIRED1"].image_purge_at is None
        assert rows["FRESH1"].evidence_image_url == fresh_path
