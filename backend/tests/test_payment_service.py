"""Mock-payment service unit tests."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import (
    BayState,
    ParkingBay,
    Payment,
    PaymentAction,
    PenaltyKind,
    Reservation,
    ReservationStatus,
)
from app.schemas.payment import CardDetails
from app.services import payment_service
from app.utils.errors import PaymentError
from app.utils.time import utcnow


def _make_reservation(session, *, user, mock_card) -> Reservation:
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.RESERVED
    res = Reservation(
        bay_id=bay.id,
        user_id=user.id,
        status=ReservationStatus.ACTIVE,
        expected_arrival_time=utcnow() + timedelta(minutes=15),
    )
    session.add(res)
    session.commit()
    return res


# ---------------------------------------------------------------------------
# validate_card
# ---------------------------------------------------------------------------


def test_validate_card_returns_row(app, session, mock_cards):
    c = mock_cards[0]
    with app.app_context():
        row = payment_service.validate_card(
            CardDetails(
                number=c.card_number,
                cvv=c.cvv,
                expiry_month=c.expiry_month,
                expiry_year=c.expiry_year,
                holder_name=c.holder_name,
            )
        )
        assert row.id == c.id


def test_validate_card_unknown_raises_card_invalid(app, mock_cards):
    with app.app_context():
        with pytest.raises(PaymentError) as exc:
            payment_service.validate_card(
                CardDetails(
                    number="9999999999999999",
                    cvv="000",
                    expiry_month=12,
                    expiry_year=2030,
                    holder_name="Nobody",
                )
            )
        assert exc.value.code == "card_invalid"


def test_validate_card_wrong_cvv_raises_card_invalid(app, mock_cards):
    c = mock_cards[0]
    with app.app_context():
        with pytest.raises(PaymentError) as exc:
            payment_service.validate_card(
                CardDetails(
                    number=c.card_number,
                    cvv="999",
                    expiry_month=c.expiry_month,
                    expiry_year=c.expiry_year,
                    holder_name=c.holder_name,
                )
            )
        assert exc.value.code == "card_invalid"


def test_validate_card_expired_raises_card_expired(app, mock_cards):
    expired = mock_cards[2]
    with app.app_context():
        with pytest.raises(PaymentError) as exc:
            payment_service.validate_card(
                CardDetails(
                    number=expired.card_number,
                    cvv=expired.cvv,
                    expiry_month=expired.expiry_month,
                    expiry_year=expired.expiry_year,
                    holder_name=expired.holder_name,
                )
            )
        assert exc.value.code == "card_expired"


# ---------------------------------------------------------------------------
# preauthorize
# ---------------------------------------------------------------------------


def test_preauthorize_debits_balance_and_inserts_row(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    c = mock_cards[0]
    starting = c.balance_cents
    with app.app_context():
        res = _make_reservation(db.session, user=user_with_plates, mock_card=c)
        card = db.session.get(type(c), c.id)
        p = payment_service.preauthorize(
            reservation_id=res.id,
            user_id=user_with_plates.id,
            card=card,
            amount_cents=1000,
        )
        db.session.commit()
        assert p.action == PaymentAction.PRE_AUTH
        assert p.amount_cents == 1000
        assert card.balance_cents == starting - 1000


def test_preauthorize_insufficient_funds_raises(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    empty = mock_cards[1]
    with app.app_context():
        res = _make_reservation(db.session, user=user_with_plates, mock_card=empty)
        card = db.session.get(type(empty), empty.id)
        with pytest.raises(PaymentError) as exc:
            payment_service.preauthorize(
                reservation_id=res.id,
                user_id=user_with_plates.id,
                card=card,
                amount_cents=1000,
            )
        assert exc.value.code == "insufficient_funds"


def test_preauthorize_idempotent(app, session, bays, user_with_plates, mock_cards):
    c = mock_cards[0]
    with app.app_context():
        res = _make_reservation(db.session, user=user_with_plates, mock_card=c)
        card = db.session.get(type(c), c.id)
        before = card.balance_cents
        p1 = payment_service.preauthorize(
            reservation_id=res.id,
            user_id=user_with_plates.id,
            card=card,
            amount_cents=1000,
        )
        db.session.commit()
        # Second call returns the same row, no second debit
        card = db.session.get(type(c), c.id)
        p2 = payment_service.preauthorize(
            reservation_id=res.id,
            user_id=user_with_plates.id,
            card=card,
            amount_cents=1000,
        )
        assert p1.id == p2.id
        assert card.balance_cents == before - 1000


# ---------------------------------------------------------------------------
# release / charge_penalty / refund
# ---------------------------------------------------------------------------


def test_release_returns_full_deposit_on_clean_cancel(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    c = mock_cards[0]
    with app.app_context():
        res = _make_reservation(db.session, user=user_with_plates, mock_card=c)
        card = db.session.get(type(c), c.id)
        starting = card.balance_cents
        payment_service.preauthorize(
            reservation_id=res.id,
            user_id=user_with_plates.id,
            card=card,
            amount_cents=1000,
        )
        db.session.commit()

        rel = payment_service.release(reservation_id=res.id, reason="clean_cancel")
        db.session.commit()
        assert rel is not None
        assert rel.amount_cents == 1000
        card = db.session.get(type(c), c.id)
        assert card.balance_cents == starting  # net zero


def test_charge_penalty_then_release_remainder(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    c = mock_cards[0]
    with app.app_context():
        res = _make_reservation(db.session, user=user_with_plates, mock_card=c)
        card = db.session.get(type(c), c.id)
        starting = card.balance_cents
        payment_service.preauthorize(
            reservation_id=res.id,
            user_id=user_with_plates.id,
            card=card,
            amount_cents=1000,
        )
        db.session.commit()

        penalty = payment_service.charge_penalty(
            reservation_id=res.id,
            penalty_kind=PenaltyKind.NO_SHOW,
            amount_cents=500,
        )
        rel = payment_service.release(reservation_id=res.id, reason="remainder")
        db.session.commit()

        assert penalty.amount_cents == 500
        assert rel is not None and rel.amount_cents == 500
        card = db.session.get(type(c), c.id)
        # net: -1000 (preauth) + 500 (release) = -500
        assert card.balance_cents == starting - 500


def test_charge_penalty_idempotent(app, session, bays, user_with_plates, mock_cards):
    c = mock_cards[0]
    with app.app_context():
        res = _make_reservation(db.session, user=user_with_plates, mock_card=c)
        card = db.session.get(type(c), c.id)
        payment_service.preauthorize(
            reservation_id=res.id,
            user_id=user_with_plates.id,
            card=card,
            amount_cents=1000,
        )
        db.session.commit()

        p1 = payment_service.charge_penalty(
            reservation_id=res.id,
            penalty_kind=PenaltyKind.NO_SHOW,
            amount_cents=500,
        )
        db.session.commit()
        p2 = payment_service.charge_penalty(
            reservation_id=res.id,
            penalty_kind=PenaltyKind.NO_SHOW,
            amount_cents=500,
        )
        assert p1.id == p2.id
        rows = (
            db.session.execute(
                db.select(Payment).where(Payment.action == PaymentAction.PENALTY_CAPTURE)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1


def test_refund_restores_remaining_deposit(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    c = mock_cards[0]
    with app.app_context():
        res = _make_reservation(db.session, user=user_with_plates, mock_card=c)
        card = db.session.get(type(c), c.id)
        starting = card.balance_cents
        payment_service.preauthorize(
            reservation_id=res.id,
            user_id=user_with_plates.id,
            card=card,
            amount_cents=1000,
        )
        db.session.commit()

        ref = payment_service.refund(reservation_id=res.id)
        db.session.commit()
        assert ref is not None and ref.amount_cents == 1000
        card = db.session.get(type(c), c.id)
        assert card.balance_cents == starting


def test_release_no_op_when_remainder_is_zero(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    """A penalty equal to the full deposit leaves nothing to release."""
    c = mock_cards[0]
    with app.app_context():
        res = _make_reservation(db.session, user=user_with_plates, mock_card=c)
        card = db.session.get(type(c), c.id)
        payment_service.preauthorize(
            reservation_id=res.id,
            user_id=user_with_plates.id,
            card=card,
            amount_cents=1000,
        )
        # Penalty = full deposit
        payment_service.charge_penalty(
            reservation_id=res.id,
            penalty_kind=PenaltyKind.NO_SHOW,
            amount_cents=1000,
        )
        payment_service.release(reservation_id=res.id, reason="remainder")
        db.session.commit()
        # A subsequent completion-release is a no-op (nothing left to give back)
        followup = payment_service.release(reservation_id=res.id, reason="completed")
        assert followup is None
