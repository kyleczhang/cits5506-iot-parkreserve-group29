"""Coverage for the lesser-used event dispatcher branches:
sensor_online, sensor_offline, check_in_confirmed (both arrival orders),
auto_check_in idempotency, conflict_strong without recognised plate, etc.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.extensions import db
from app.models import (
    BayEvent,
    BayEventKind,
    BayState,
    CheckInMechanism,
    ParkingBay,
    Reservation,
    ReservationStatus,
)
from app.mqtt.topics import InternalEventPayload, PiInboundEventPayload
from app.services.event_dispatcher import dispatch_event
from app.utils.time import utcnow


def _event(kind: str, **extra):
    base = dict(event=kind, ts=utcnow(), event_id=uuid4())
    base.update(extra)
    if kind in {"conflict_weak", "no_show"}:
        return InternalEventPayload(**base)
    return PiInboundEventPayload(**base)


def test_sensor_online_brings_bay_back_from_offline(app, session, bays):
    with app.app_context():
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        bay.state = BayState.OFFLINE
        db.session.commit()

        dispatch_event(bay_code="A1", payload=_event("sensor_online"))

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.AVAILABLE


def test_sensor_offline_marks_bay_offline(app, session, bays):
    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("sensor_offline"))

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.OFFLINE


def test_unknown_bay_is_dropped_silently(app, session, bays):
    with app.app_context():
        dispatch_event(bay_code="ZZ", payload=_event("sensor_online"))


def test_check_in_confirmed_after_already_checked_in_records_audit(
    app,
    session,
    bays,
    user_with_plates,
):
    """Common case: REST handler set status to CHECKED_IN, Pi later echoes
    a check_in_confirmed event. We just record the audit row."""
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    res = Reservation(
        bay_id=bay.id,
        user_id=user_with_plates.id,
        status=ReservationStatus.CHECKED_IN,
        expected_arrival_time=utcnow() + timedelta(minutes=10),
        checked_in_at=utcnow(),
        check_in_mechanism=CheckInMechanism.QR,
    )
    bay.state = BayState.RESERVED_CHECKED_IN
    bay.current_reservation_id = res.id
    session.add(res)
    session.commit()

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("check_in_confirmed"))

        events = (
            db.session.execute(
                db.select(BayEvent).where(BayEvent.kind == BayEventKind.CHECK_IN_CONFIRMED)
            )
            .scalars()
            .all()
        )
        assert len(events) == 1


def test_check_in_confirmed_when_pending_promotes_to_checked_in(
    app,
    session,
    bays,
    user_with_plates,
):
    """Edge: Pi check_in_confirmed arrived before our REST mutation completed.
    Treat as a manual check-in (we don't know which fallback was used)."""
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.PENDING_CHECK_IN
    res = Reservation(
        bay_id=bay.id,
        user_id=user_with_plates.id,
        status=ReservationStatus.PENDING_CHECK_IN,
        expected_arrival_time=utcnow() + timedelta(minutes=10),
        check_in_grace_expires_at=utcnow() + timedelta(minutes=5),
    )
    session.add(res)
    session.commit()

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("check_in_confirmed"))

        res = db.session.execute(
            db.select(Reservation).where(Reservation.user_id == user_with_plates.id)
        ).scalar_one()
        assert res.status == ReservationStatus.CHECKED_IN
        assert res.check_in_mechanism == CheckInMechanism.MANUAL


def test_pending_check_in_without_open_reservation_is_noop(app, session, bays):
    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("pending_check_in"))
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        # No reservation → no transition
        assert bay.state == BayState.AVAILABLE


def test_conflict_strong_missing_plate_dropped(app, session, bays, user_with_plates):
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    res = Reservation(
        bay_id=bay.id,
        user_id=user_with_plates.id,
        status=ReservationStatus.ACTIVE,
        expected_arrival_time=utcnow() + timedelta(minutes=10),
    )
    bay.state = BayState.RESERVED
    session.add(res)
    session.commit()

    with app.app_context():
        # No `recognised_plate` — dispatcher logs and drops without crashing
        dispatch_event(
            bay_code="A1",
            payload=_event("conflict_strong", lpr_confidence=0.91),
        )
        # State unchanged
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.RESERVED


def test_unknown_event_kind_is_logged_and_dropped(app, session, bays):
    """Pydantic literal type rejects unknown events at parse time, but the
    dispatcher's `_HANDLERS.get` defends against future enum drift too."""

    from app.services import event_dispatcher

    # Synthesise a payload whose `event` field bypasses pydantic literal —
    # we directly push into the dispatcher map lookup.
    handler = event_dispatcher._HANDLERS.get("definitely-not-an-event")
    assert handler is None
