"""Safety-net sweeper tests."""

from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.jobs.reconcile_reservations import run_once
from app.models import (
    BayState,
    ParkingBay,
    Payment,
    PaymentAction,
    PenaltyKind,
    Reservation,
    ReservationStatus,
)
from app.utils.time import utcnow


def _seed_with_preauth(session, *, bay, user, mock_card, status, **res_kwargs):
    res = Reservation(
        bay_id=bay.id,
        user_id=user.id,
        status=status,
        **res_kwargs,
    )
    session.add(res)
    session.flush()
    pa = Payment(
        reservation_id=res.id,
        user_id=user.id,
        mock_card_id=mock_card.id,
        action=PaymentAction.PRE_AUTH,
        amount_cents=1000,
        idempotency_key=f"pre_auth:{res.id}",
    )
    mock_card.balance_cents -= 1000
    session.add(pa)
    session.commit()
    return res


def test_sweeper_synthesises_no_show_when_pi_event_missed(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.AVAILABLE
    res = _seed_with_preauth(
        session,
        bay=bay,
        user=user_with_plates,
        mock_card=mock_cards[0],
        status=ReservationStatus.ACTIVE,
        booked_at=utcnow() - timedelta(minutes=20),
        expected_arrival_time=utcnow() - timedelta(minutes=10),
    )

    with app.app_context():
        result = run_once()

    assert result["no_show"] >= 1
    with app.app_context():
        refreshed = db.session.get(Reservation, res.id)
        assert refreshed.status == ReservationStatus.EXPIRED_NO_SHOW
        penalties = (
            db.session.execute(
                db.select(Payment).where(Payment.action == PaymentAction.PENALTY_CAPTURE)
            )
            .scalars()
            .all()
        )
        assert any(p.penalty_kind == PenaltyKind.NO_SHOW for p in penalties)


def test_sweeper_synthesises_only_weak_conflict_never_strong(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.PENDING_CHECK_IN
    res = _seed_with_preauth(
        session,
        bay=bay,
        user=user_with_plates,
        mock_card=mock_cards[0],
        status=ReservationStatus.PENDING_CHECK_IN,
        booked_at=utcnow() - timedelta(minutes=30),
        expected_arrival_time=utcnow() + timedelta(minutes=5),
        check_in_grace_expires_at=utcnow() - timedelta(minutes=1),
    )

    with app.app_context():
        result = run_once()

    assert result["conflict_weak"] >= 1
    with app.app_context():
        refreshed = db.session.get(Reservation, res.id)
        assert refreshed.status == ReservationStatus.IN_CONFLICT
        penalties = (
            db.session.execute(
                db.select(Payment).where(Payment.action == PaymentAction.PENALTY_CAPTURE)
            )
            .scalars()
            .all()
        )
        assert any(p.penalty_kind == PenaltyKind.WEAK_CONFLICT for p in penalties)


def test_sweeper_idempotent_does_not_double_charge(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.AVAILABLE
    _seed_with_preauth(
        session,
        bay=bay,
        user=user_with_plates,
        mock_card=mock_cards[0],
        status=ReservationStatus.ACTIVE,
        booked_at=utcnow() - timedelta(minutes=20),
        expected_arrival_time=utcnow() - timedelta(minutes=10),
    )

    with app.app_context():
        run_once()
        run_once()
        run_once()
        penalties = (
            db.session.execute(
                db.select(Payment).where(Payment.action == PaymentAction.PENALTY_CAPTURE)
            )
            .scalars()
            .all()
        )
        assert len(penalties) == 1
