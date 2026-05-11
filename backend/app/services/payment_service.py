"""Mock-payment service.

In-process mock-bank simulator. Five operations:

  * ``validate_card`` — lookup + lock by number/CVV/holder; expiry check
  * ``preauthorize`` — debit deposit from mock card; insert ``pre_auth`` row
  * ``release``      — restore remaining deposit; insert ``release`` row
  * ``charge_penalty`` — insert ``penalty_capture`` row (card unchanged)
  * ``refund``       — restore full remaining deposit; insert ``refund`` row

Every operation is **idempotent on a deterministic ``idempotency_key``**:
MQTT redeliveries, sweeper retries, network
blips, and user double-clicks all collapse to a single ledger row.

A non-pre_auth call is a **no-op** when the deposit has already been fully
accounted for (e.g. release-on-completion after the no_show penalty already
captured-and-released the deposit).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select

from app.extensions import db
from app.models import MockCard, Payment, PaymentAction, PenaltyKind
from app.schemas.payment import CardDetails
from app.utils.errors import PaymentError
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Card validation
# ---------------------------------------------------------------------------


def validate_card(card: CardDetails) -> MockCard:
    """Look up the card in ``mock_cards`` and acquire a row-level lock.

    Raises :class:`PaymentError` on unknown card / wrong CVV / expired card.
    The lock makes concurrent bookings against the same card serial.
    """
    row = db.session.execute(
        select(MockCard)
        .where(
            MockCard.card_number == card.number,
            MockCard.cvv == card.cvv,
            MockCard.holder_name == card.holder_name,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise PaymentError("card not recognised", code="card_invalid")
    if row.expiry_year != card.expiry_year or row.expiry_month != card.expiry_month:
        raise PaymentError("card not recognised", code="card_invalid")

    now = utcnow()
    if (row.expiry_year, row.expiry_month) < (now.year, now.month):
        raise PaymentError("card has expired", code="card_expired")
    return row


# ---------------------------------------------------------------------------
# Pre-authorize (deposit hold at booking)
# ---------------------------------------------------------------------------


def preauthorize(
    *,
    reservation_id: UUID,
    user_id: UUID,
    card: MockCard,
    amount_cents: int,
) -> Payment:
    """Debit ``amount_cents`` from the locked card and insert a ``pre_auth``
    row, idempotent on ``pre_auth:<reservation_id>``.

    Caller must already hold the card lock (via :func:`validate_card`).
    Raises :class:`PaymentError` (``insufficient_funds``) if the card has
    less than ``amount_cents`` available.
    """
    if card.balance_cents < amount_cents:
        raise PaymentError(
            "card has insufficient funds for the deposit",
            code="insufficient_funds",
        )

    idempotency_key = f"pre_auth:{reservation_id}"
    existing = _existing(idempotency_key)
    if existing is not None:
        return existing

    card.balance_cents -= amount_cents
    payment = Payment(
        reservation_id=reservation_id,
        user_id=user_id,
        mock_card_id=card.id,
        action=PaymentAction.PRE_AUTH,
        amount_cents=amount_cents,
        idempotency_key=idempotency_key,
    )
    db.session.add(payment)
    db.session.flush()
    return payment


# ---------------------------------------------------------------------------
# Release (clean cancel / completion / post-penalty remainder)
# ---------------------------------------------------------------------------


def release(
    *,
    reservation_id: UUID,
    reason: str,
    source_event_id: UUID | None = None,
) -> Payment | None:
    """Return the *remaining* deposit to the card.

    ``reason`` is one of ``"clean_cancel"``, ``"completed"``, ``"remainder"``.
    Idempotent on ``release:<reservation_id>:<reason>``. No-op (returns None)
    when the remaining deposit is zero — the spent amount already accounts
    for the entire pre-auth (e.g. a $10 penalty that consumed a $10 deposit).
    """
    pre_auth = _pre_auth(reservation_id)
    if pre_auth is None:
        return None

    idempotency_key = f"release:{reservation_id}:{reason}"
    existing = _existing(idempotency_key)
    if existing is not None:
        return existing

    remaining = _remaining(reservation_id, pre_auth.amount_cents)
    if remaining <= 0:
        return None

    card = db.session.execute(
        select(MockCard).where(MockCard.id == pre_auth.mock_card_id).with_for_update()
    ).scalar_one()
    card.balance_cents += remaining

    payment = Payment(
        reservation_id=reservation_id,
        user_id=pre_auth.user_id,
        mock_card_id=card.id,
        parent_payment_id=pre_auth.id,
        action=PaymentAction.RELEASE,
        amount_cents=remaining,
        idempotency_key=idempotency_key,
        source_event_id=source_event_id,
    )
    db.session.add(payment)
    db.session.flush()
    return payment


# ---------------------------------------------------------------------------
# Penalty capture (late_cancel / no_show / weak_conflict)
# ---------------------------------------------------------------------------


def charge_penalty(
    *,
    reservation_id: UUID,
    penalty_kind: PenaltyKind,
    amount_cents: int,
    source_event_id: UUID | None = None,
) -> Payment | None:
    """Insert a ``penalty_capture`` row, idempotent on
    ``penalty_capture:<reservation_id>:<penalty_kind>``.

    The card balance is NOT changed — the penalty is a "spent" amount that
    will be reflected in a smaller subsequent ``release`` row. Capped at the
    remaining deposit (so a $5 penalty against a $3 remainder captures $3).
    """
    pre_auth = _pre_auth(reservation_id)
    if pre_auth is None:
        return None

    idempotency_key = f"penalty_capture:{reservation_id}:{penalty_kind.value}"
    existing = _existing(idempotency_key)
    if existing is not None:
        return existing

    remaining = _remaining(reservation_id, pre_auth.amount_cents)
    if remaining <= 0:
        return None
    captured = min(amount_cents, remaining)

    payment = Payment(
        reservation_id=reservation_id,
        user_id=pre_auth.user_id,
        mock_card_id=pre_auth.mock_card_id,
        parent_payment_id=pre_auth.id,
        action=PaymentAction.PENALTY_CAPTURE,
        penalty_kind=penalty_kind,
        amount_cents=captured,
        idempotency_key=idempotency_key,
        source_event_id=source_event_id,
    )
    db.session.add(payment)
    db.session.flush()
    return payment


# ---------------------------------------------------------------------------
# Refund (strong-conflict victim — full deposit restored)
# ---------------------------------------------------------------------------


def refund(
    *,
    reservation_id: UUID,
    source_event_id: UUID | None = None,
) -> Payment | None:
    """Restore the *remaining* deposit as a victim refund.

    Idempotent on ``refund:<reservation_id>:strong_conflict``. Semantically
    equivalent to :func:`release` but flagged separately for the receipt.
    """
    pre_auth = _pre_auth(reservation_id)
    if pre_auth is None:
        return None

    idempotency_key = f"refund:{reservation_id}:strong_conflict"
    existing = _existing(idempotency_key)
    if existing is not None:
        return existing

    remaining = _remaining(reservation_id, pre_auth.amount_cents)
    if remaining <= 0:
        return None

    card = db.session.execute(
        select(MockCard).where(MockCard.id == pre_auth.mock_card_id).with_for_update()
    ).scalar_one()
    card.balance_cents += remaining

    payment = Payment(
        reservation_id=reservation_id,
        user_id=pre_auth.user_id,
        mock_card_id=card.id,
        parent_payment_id=pre_auth.id,
        action=PaymentAction.REFUND,
        amount_cents=remaining,
        idempotency_key=idempotency_key,
        source_event_id=source_event_id,
    )
    db.session.add(payment)
    db.session.flush()
    return payment


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def list_for_user(user_id: UUID) -> list[Payment]:
    return list(
        db.session.execute(
            select(Payment).where(Payment.user_id == user_id).order_by(Payment.occurred_at.desc())
        ).scalars()
    )


def get_for_user(*, user_id: UUID, payment_id: UUID) -> Payment | None:
    return db.session.execute(
        select(Payment).where(Payment.id == payment_id, Payment.user_id == user_id)
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _pre_auth(reservation_id: UUID) -> Payment | None:
    return db.session.execute(
        select(Payment).where(
            Payment.reservation_id == reservation_id,
            Payment.action == PaymentAction.PRE_AUTH,
        )
    ).scalar_one_or_none()


def _existing(idempotency_key: str) -> Payment | None:
    return db.session.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    ).scalar_one_or_none()


def _remaining(reservation_id: UUID, pre_auth_amount: int) -> int:
    """``pre_auth.amount - SUM(release + refund + penalty_capture)``."""
    spent = db.session.execute(
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
            Payment.reservation_id == reservation_id,
            Payment.action.in_(
                [
                    PaymentAction.RELEASE,
                    PaymentAction.REFUND,
                    PaymentAction.PENALTY_CAPTURE,
                ]
            ),
        )
    ).scalar_one()
    return max(int(pre_auth_amount) - int(spent), 0)


__all__ = [
    "validate_card",
    "preauthorize",
    "release",
    "charge_penalty",
    "refund",
    "list_for_user",
    "get_for_user",
]
