"""conflict_service: resolution, evidence-upload-before-MQTT, lookup helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.extensions import db
from app.models import (
    ConflictKind,
    ConflictResolution,
    ParkingBay,
)
from app.services import conflict_service
from app.utils.errors import ConflictError, NotFoundError, ValidationError
from app.utils.time import utcnow


def _bay(session, code="A1"):
    return session.execute(db.select(ParkingBay).where(ParkingBay.code == code)).scalar_one()


def test_resolve_strong_with_user_check_in_rejected(app, session, bays):
    with app.app_context():
        bay = _bay(db.session)
        c = conflict_service.upsert_strong(
            bay=bay,
            reservation_id=None,
            source_event_id=uuid4(),
            recognised_plate="ZZZ999",
            lpr_confidence=0.91,
            detected_at=utcnow(),
        )
        db.session.commit()
        with pytest.raises(ConflictError) as exc:
            conflict_service.resolve(
                c,
                resolution=ConflictResolution.USER_ARRIVED_AND_CHECKED_IN,
            )
        assert exc.value.code == "strong_conflict_user_resolution_invalid"


def test_resolve_weak_with_user_check_in_ok(app, session, bays):
    with app.app_context():
        bay = _bay(db.session)
        c = conflict_service.upsert_weak(
            bay=bay,
            reservation_id=None,
            source_event_id=uuid4(),
            detected_at=utcnow(),
        )
        db.session.commit()
        conflict_service.resolve(
            c,
            resolution=ConflictResolution.USER_ARRIVED_AND_CHECKED_IN,
        )
        db.session.commit()
        assert c.resolved_at is not None
        assert c.resolution == ConflictResolution.USER_ARRIVED_AND_CHECKED_IN


def test_attach_evidence_image_before_mqtt_event_creates_placeholder(
    app,
    session,
    bays,
    _evidence_dir,
):
    with app.app_context():
        bay = _bay(db.session)
        eid = uuid4()
        c = conflict_service.attach_evidence_image(
            bay=bay,
            source_event_id=eid,
            image_bytes=b"\xff\xd8\xff fake",
            recognised_plate="ZZZ999",
        )
        db.session.commit()

        assert c.kind == ConflictKind.STRONG
        assert c.recognised_plate == "ZZZ999"
        assert c.evidence_image_url is not None
        assert c.image_purge_at is not None


def test_attach_evidence_image_before_mqtt_without_plate_rejected(app, session, bays):
    with app.app_context():
        bay = _bay(db.session)
        with pytest.raises(ValidationError) as exc:
            conflict_service.attach_evidence_image(
                bay=bay,
                source_event_id=uuid4(),
                image_bytes=b"\xff\xd8\xff fake",
                recognised_plate=None,
            )
        assert exc.value.code == "missing_recognised_plate"


def test_get_unknown_conflict_404(app):
    with app.app_context():
        with pytest.raises(NotFoundError):
            conflict_service.get_by_id(uuid4())


def test_purge_with_no_expired_returns_empty(app, session, bays):
    with app.app_context():
        purged = conflict_service.purge_expired_evidence()
        assert purged == []
