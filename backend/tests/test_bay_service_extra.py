"""bay_service.apply_state completion-inference path coverage.

When a bay transitions reserved_checked_in → available, an open
CHECKED_IN reservation must be transitioned to COMPLETED.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.extensions import db
from app.models import (
    BayState,
    CheckInMechanism,
    Conflict,
    ConflictKind,
    ParkingBay,
    Reservation,
    ReservationStatus,
)
from app.mqtt.topics import StatePayload
from app.services.bay_service import apply_state
from app.utils.time import utcnow


def test_state_back_to_available_completes_open_reservation(
    app,
    session,
    bays,
    user_with_plates,
    monkeypatch,
):
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.RESERVED_CHECKED_IN
    booked = utcnow() - timedelta(minutes=20)
    res = Reservation(
        bay_id=bay.id,
        user_id=user_with_plates.id,
        status=ReservationStatus.CHECKED_IN,
        booked_at=booked,
        expected_arrival_time=booked + timedelta(minutes=15),
        checked_in_at=utcnow() - timedelta(minutes=1),
        check_in_mechanism=CheckInMechanism.AUTO_LPR,
        check_in_recognised_plate="ABC123",
    )
    bay.current_reservation_id = res.id
    session.add(res)
    session.commit()

    with app.app_context():
        apply_state(
            bay_code="A1",
            payload=StatePayload(
                state="available",
                last_distance_cm=30.0,
                ts=utcnow(),
                event_id=uuid4(),
            ),
        )

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.AVAILABLE
        assert bay.current_reservation_id is None

        res = db.session.execute(
            db.select(Reservation).where(Reservation.user_id == user_with_plates.id)
        ).scalar_one()
        assert res.status == ReservationStatus.COMPLETED
        assert res.completed_at is not None
    assert len(published) == 1
    assert published[0]["bay_code"] == "A1"
    assert published[0]["action"] == "release"
    assert published[0]["reservation"].id == res.id
    assert published[0]["user"].id == user_with_plates.id
    assert published[0]["bound_plates"] == []
    assert published[0]["reason"] == "completed"


def test_state_back_to_available_after_weak_conflict_publishes_abandoned_release(
    app,
    session,
    bays,
    user_with_plates,
    monkeypatch,
):
    """A weak-conflict bay that clears back to AVAILABLE is treated as
    abandoned — the holder failed to manually check in within the grace
    window. (Strong conflicts go through the restore branch instead.)"""
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    booked = utcnow() - timedelta(minutes=20)
    res = Reservation(
        bay_id=bay.id,
        user_id=user_with_plates.id,
        status=ReservationStatus.IN_CONFLICT,
        booked_at=booked,
        expected_arrival_time=booked + timedelta(minutes=15),
    )
    bay.state = BayState.CONFLICT
    bay.current_reservation_id = res.id
    session.add(res)
    session.flush()
    # Explicit weak conflict on this bay — guards against the strong-restore
    # branch accidentally firing here.
    session.add(
        Conflict(
            bay_id=bay.id,
            reservation_id=res.id,
            kind=ConflictKind.WEAK,
            source_event_id=uuid4(),
            detected_at=utcnow(),
        )
    )
    session.commit()

    with app.app_context():
        apply_state(
            bay_code="A1",
            payload=StatePayload(
                state="available",
                last_distance_cm=30.0,
                ts=utcnow(),
                event_id=uuid4(),
            ),
        )

        refreshed = db.session.get(Reservation, res.id)
        assert refreshed.status == ReservationStatus.COMPLETED
        assert refreshed.completed_at is not None

    assert len(published) == 1
    assert published[0]["bay_code"] == "A1"
    assert published[0]["action"] == "release"
    assert published[0]["reservation"].id == res.id
    assert published[0]["user"].id == user_with_plates.id
    assert published[0]["bound_plates"] == []
    assert published[0]["reason"] == "abandoned"


def test_state_no_change_persists_reading_only(app, session, bays):
    """When the new state equals the old state, no STATE_CHANGED event is
    written; only a sensor reading + an updated last_distance_cm."""
    from app.models import BayEvent, BayEventKind, SensorReading

    with app.app_context():
        # First write transitions AVAILABLE → AVAILABLE = no STATE_CHANGED
        apply_state(
            bay_code="A1",
            payload=StatePayload(
                state="available",
                last_distance_cm=30.0,
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
        assert len(events) == 0

        readings = db.session.execute(db.select(SensorReading)).scalars().all()
        assert len(readings) == 1
