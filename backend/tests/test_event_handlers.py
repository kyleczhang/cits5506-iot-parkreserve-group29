"""Pi → backend event-handler tests.

Each handler is invoked with a synthetic EventPayload — no MQTT broker is
required for these unit tests. The Pi is the authoritative state machine; we
verify the backend's mirror + business-rule reactions, including the
mock-payment penalty / refund side-effects.
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
    Conflict,
    ConflictKind,
    ParkingBay,
    Payment,
    PaymentAction,
    PenaltyKind,
    Reservation,
    ReservationStatus,
)
from app.mqtt.topics import InternalEventPayload, PiInboundEventPayload
from app.services.event_dispatcher import dispatch_event
from app.utils.time import utcnow

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_active_reservation(session, *, bay_code: str, user) -> Reservation:
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == bay_code)).scalar_one()
    reservation = Reservation(
        bay_id=bay.id,
        user_id=user.id,
        status=ReservationStatus.ACTIVE,
        expected_arrival_time=utcnow() + timedelta(minutes=10),
    )
    session.add(reservation)
    bay.state = BayState.RESERVED
    bay.current_reservation_id = reservation.id
    session.commit()
    return reservation


def _add_preauth(
    session, reservation: Reservation, mock_card, *, amount_cents: int = 1000
) -> Payment:
    """Insert a `pre_auth` payment row so penalty / refund handlers have
    something to charge against (mirrors what reservation_service.create
    does when called via the API)."""
    p = Payment(
        reservation_id=reservation.id,
        user_id=reservation.user_id,
        mock_card_id=mock_card.id,
        action=PaymentAction.PRE_AUTH,
        amount_cents=amount_cents,
        idempotency_key=f"pre_auth:{reservation.id}",
    )
    mock_card.balance_cents -= amount_cents
    session.add(p)
    session.commit()
    return p


def _event(kind: str, **extra):
    base = dict(event=kind, ts=utcnow(), event_id=uuid4())
    base.update(extra)
    if kind in {"conflict_weak", "no_show"}:
        return InternalEventPayload(**base)
    return PiInboundEventPayload(**base)


# ---------------------------------------------------------------------------
# pending_check_in
# ---------------------------------------------------------------------------


def test_pending_check_in_transitions_reservation_and_sets_grace(
    app,
    session,
    bays,
    user_with_plates,
):
    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("pending_check_in"))

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.PENDING_CHECK_IN
        assert res.check_in_grace_expires_at is not None

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.PENDING_CHECK_IN

        events = (
            db.session.execute(
                db.select(BayEvent).where(
                    BayEvent.bay_id == bay.id, BayEvent.kind == BayEventKind.PENDING_CHECK_IN
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1


# ---------------------------------------------------------------------------
# auto_check_in
# ---------------------------------------------------------------------------


def test_auto_check_in_transitions_to_checked_in_with_plate(
    app,
    session,
    bays,
    user_with_plates,
):
    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)

    with app.app_context():
        dispatch_event(
            bay_code="A1",
            payload=_event("auto_check_in", recognised_plate="ABC123", lpr_confidence=0.95),
        )

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.CHECKED_IN
        assert res.check_in_mechanism == CheckInMechanism.AUTO_LPR
        assert res.check_in_recognised_plate == "ABC123"
        assert res.checked_in_at is not None

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.RESERVED_CHECKED_IN

        events = (
            db.session.execute(
                db.select(BayEvent).where(BayEvent.kind == BayEventKind.AUTO_CHECK_IN)
            )
            .scalars()
            .all()
        )
        assert len(events) == 1


def test_auto_check_in_replay_is_idempotent(app, session, bays, user_with_plates):
    _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    payload = _event("auto_check_in", recognised_plate="ABC123", lpr_confidence=0.95)

    with app.app_context():
        dispatch_event(bay_code="A1", payload=payload)
        dispatch_event(bay_code="A1", payload=payload)

        events = (
            db.session.execute(
                db.select(BayEvent).where(BayEvent.kind == BayEventKind.AUTO_CHECK_IN)
            )
            .scalars()
            .all()
        )
        assert len(events) == 1


# ---------------------------------------------------------------------------
# conflict_strong (not a user penalty — refund issued)
# ---------------------------------------------------------------------------


def test_conflict_strong_issues_refund_and_logs_incident(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

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

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.IN_CONFLICT

        conflicts = db.session.execute(db.select(Conflict)).scalars().all()
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c.kind == ConflictKind.STRONG
        assert c.recognised_plate == "ZZZ999"

        # Refund row issued, no penalty because the user is the victim.
        rows = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(r.action.value for r in rows)
        assert actions == ["pre_auth", "refund"]
        assert all(r.penalty_kind is None for r in rows)
        refund = next(r for r in rows if r.action == PaymentAction.REFUND)
        assert refund.amount_cents == 1000


def test_conflict_strong_replay_is_idempotent(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])
    payload = _event("conflict_strong", recognised_plate="ZZZ999", lpr_confidence=0.91)
    with app.app_context():
        dispatch_event(bay_code="A1", payload=payload)
        dispatch_event(bay_code="A1", payload=payload)

        conflicts = db.session.execute(db.select(Conflict)).scalars().all()
        assert len(conflicts) == 1
        # Refund only once
        refunds = (
            db.session.execute(db.select(Payment).where(Payment.action == PaymentAction.REFUND))
            .scalars()
            .all()
        )
        assert len(refunds) == 1


# ---------------------------------------------------------------------------
# conflict_weak (is a user penalty)
# ---------------------------------------------------------------------------


def test_conflict_weak_captures_penalty_and_releases_remainder(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    from app.services import notification_service

    released: list[tuple[int, str]] = []
    published: list[dict] = []
    monkeypatch.setattr(
        notification_service,
        "push_deposit_released",
        lambda *, amount_cents, reason, **_: released.append((amount_cents, reason)),
    )
    monkeypatch.setattr(
        "app.services.event_dispatcher.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])
    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("pending_check_in"))
        dispatch_event(bay_code="A1", payload=_event("conflict_weak"))

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.CONFLICT

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.IN_CONFLICT

        conflicts = db.session.execute(db.select(Conflict)).scalars().all()
        assert len(conflicts) == 1
        assert conflicts[0].kind == ConflictKind.WEAK
        assert conflicts[0].recognised_plate is None

        rows = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(r.action.value for r in rows)
        assert actions == ["penalty_capture", "pre_auth", "release"]
        penalty = next(r for r in rows if r.action == PaymentAction.PENALTY_CAPTURE)
        assert penalty.penalty_kind == PenaltyKind.WEAK_CONFLICT
        assert penalty.amount_cents == 500
        assert penalty.user_id == user_with_plates.id
    assert released == [(500, "remainder")]
    assert len(published) == 1
    assert published[0]["bay_code"] == "A1"
    assert published[0]["action"] == "expire_check_in"
    assert published[0]["reservation"].id == reservation.id
    assert published[0]["user"].id == user_with_plates.id
    assert published[0]["bound_plates"] == ["ABC123", "XYZ789"]


def test_conflict_weak_skips_release_event_when_penalty_consumes_full_deposit(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    from app.services import notification_service

    released: list[tuple[int, str]] = []
    monkeypatch.setattr(
        notification_service,
        "push_deposit_released",
        lambda *, amount_cents, reason, **_: released.append((amount_cents, reason)),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0], amount_cents=500)
    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("pending_check_in"))
        dispatch_event(bay_code="A1", payload=_event("conflict_weak"))

        rows = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(r.action.value for r in rows)
        assert actions == ["penalty_capture", "pre_auth"]
    assert released == []


# ---------------------------------------------------------------------------
# no_show
# ---------------------------------------------------------------------------


def test_no_show_expires_reservation_and_captures_penalty(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    from app.services import notification_service

    released: list[tuple[int, str]] = []
    published: list[dict] = []
    monkeypatch.setattr(
        notification_service,
        "push_deposit_released",
        lambda *, amount_cents, reason, **_: released.append((amount_cents, reason)),
    )
    monkeypatch.setattr(
        "app.services.event_dispatcher.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("no_show"))

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.EXPIRED_NO_SHOW

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.AVAILABLE
        assert bay.current_reservation_id is None

        rows = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(r.action.value for r in rows)
        assert actions == ["penalty_capture", "pre_auth", "release"]
        penalty = next(r for r in rows if r.action == PaymentAction.PENALTY_CAPTURE)
        assert penalty.penalty_kind == PenaltyKind.NO_SHOW
    assert released == [(500, "remainder")]
    assert len(published) == 1
    assert published[0]["bay_code"] == "A1"
    assert published[0]["action"] == "release"
    assert published[0]["reservation"].id == reservation.id
    assert published[0]["user"].id == user_with_plates.id
    assert published[0]["bound_plates"] == []
    assert published[0]["reason"] == "no_show"


def test_no_show_skips_release_event_when_penalty_consumes_full_deposit(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    from app.services import notification_service

    released: list[tuple[int, str]] = []
    monkeypatch.setattr(
        notification_service,
        "push_deposit_released",
        lambda *, amount_cents, reason, **_: released.append((amount_cents, reason)),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0], amount_cents=500)

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_event("no_show"))

        rows = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(r.action.value for r in rows)
        assert actions == ["penalty_capture", "pre_auth"]
    assert released == []
