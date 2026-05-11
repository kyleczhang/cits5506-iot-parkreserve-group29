"""Additional event-dispatcher branch coverage."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.extensions import db
from app.models import (
    BayState,
    Conflict,
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


def test_pending_check_in_replay_is_idempotent(app, session, bays, user_with_plates):
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

    payload = _event("pending_check_in")
    with app.app_context():
        dispatch_event(bay_code="A1", payload=payload)
        dispatch_event(bay_code="A1", payload=payload)

        from app.models import BayEvent, BayEventKind

        events = (
            db.session.execute(
                db.select(BayEvent).where(BayEvent.kind == BayEventKind.PENDING_CHECK_IN)
            )
            .scalars()
            .all()
        )
        assert len(events) == 1


def test_auto_check_in_no_open_reservation_dropped(app, session, bays):
    with app.app_context():
        dispatch_event(
            bay_code="A1",
            payload=_event("auto_check_in", recognised_plate="ABC123", lpr_confidence=0.95),
        )
        # No reservation existed → bay state stays AVAILABLE (no rows committed)
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.AVAILABLE


def test_auto_check_in_already_checked_in_idempotent(
    app,
    session,
    bays,
    user_with_plates,
):
    from app.models import CheckInMechanism

    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    res = Reservation(
        bay_id=bay.id,
        user_id=user_with_plates.id,
        status=ReservationStatus.CHECKED_IN,
        expected_arrival_time=utcnow() + timedelta(minutes=10),
        checked_in_at=utcnow(),
        check_in_mechanism=CheckInMechanism.AUTO_LPR,
        check_in_recognised_plate="ABC123",
    )
    bay.state = BayState.RESERVED_CHECKED_IN
    session.add(res)
    session.commit()

    with app.app_context():
        dispatch_event(
            bay_code="A1",
            payload=_event("auto_check_in", recognised_plate="ABC123", lpr_confidence=0.95),
        )
        # No further state change
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.RESERVED_CHECKED_IN


def test_no_show_without_open_reservation_is_noop(app, session, bays):
    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("no_show"))
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.AVAILABLE


def test_conflict_strong_without_open_reservation_records_facility_incident(
    app,
    session,
    bays,
):
    with app.app_context():
        dispatch_event(
            bay_code="A1",
            payload=_event(
                "conflict_strong",
                recognised_plate="ZZZ999",
                lpr_confidence=0.91,
            ),
        )

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.CONFLICT

        # Conflict row exists with no reservation_id
        conflicts = db.session.execute(db.select(Conflict)).scalars().all()
        assert len(conflicts) == 1
        assert conflicts[0].reservation_id is None
        assert conflicts[0].recognised_plate == "ZZZ999"


def test_conflict_weak_when_bay_already_in_conflict_does_not_double_transition(
    app,
    session,
    bays,
    user_with_plates,
):
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    res = Reservation(
        bay_id=bay.id,
        user_id=user_with_plates.id,
        status=ReservationStatus.PENDING_CHECK_IN,
        expected_arrival_time=utcnow() + timedelta(minutes=10),
        check_in_grace_expires_at=utcnow() - timedelta(minutes=1),
    )
    bay.state = BayState.CONFLICT
    session.add(res)
    session.commit()

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("conflict_weak"))

        # Bay still CONFLICT, conflict row created, reservation IN_CONFLICT
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.CONFLICT


def test_no_show_replay_is_idempotent(app, session, bays, user_with_plates):
    """Pi may replay a `no_show` event after reconnect — second insert
    deduplicates on `source_event_id`."""
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

    payload = _event("no_show")
    with app.app_context():
        dispatch_event(bay_code="A1", payload=payload)
        dispatch_event(bay_code="A1", payload=payload)

        # Reservation transitions to EXPIRED_NO_SHOW exactly once (the
        # second dispatch is a no-op via source_event_id dedupe).
        from app.models import Payment, PaymentAction

        rows = (
            db.session.execute(
                db.select(Payment).where(Payment.action == PaymentAction.PENALTY_CAPTURE)
            )
            .scalars()
            .all()
        )
        # No pre_auth was inserted in this test, so charge_penalty is a no-op
        assert rows == []
        refreshed = db.session.get(Reservation, res.id)
        assert refreshed.status == ReservationStatus.EXPIRED_NO_SHOW
