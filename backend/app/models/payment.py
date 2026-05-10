from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class PaymentAction(str, enum.Enum):
    PRE_AUTH = "pre_auth"
    RELEASE = "release"
    REFUND = "refund"
    PENALTY_CAPTURE = "penalty_capture"


class PaymentStatus(str, enum.Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    VOIDED = "voided"


class PenaltyKind(str, enum.Enum):
    LATE_CANCEL = "late_cancel"
    NO_SHOW = "no_show"
    WEAK_CONFLICT = "weak_conflict"
    # NOTE: strong-evidence conflicts are NEVER a user penalty (proposal §5.5).
    # The `payments_penalty_kind_only_for_penalty` CHECK enforces this at the DB.


class Payment(db.Model):
    """Single ledger row for every payment-service action (database-design §3.11).

    Idempotent on `idempotency_key`. Each non-`pre_auth` row references its
    parent `pre_auth` via `parent_payment_id`. `penalty_kind` is set iff
    `action='penalty_capture'`.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="payments_amount_nonneg"),
        CheckConstraint(
            "(action = 'pre_auth' AND parent_payment_id IS NULL)"
            " OR (action <> 'pre_auth' AND parent_payment_id IS NOT NULL)",
            name="payments_parent_required",
        ),
        CheckConstraint(
            "(action = 'penalty_capture' AND penalty_kind IS NOT NULL)"
            " OR (action <> 'penalty_capture' AND penalty_kind IS NULL)",
            name="payments_penalty_kind_only_for_penalty",
        ),
        Index("payments_reservation_idx", "reservation_id", "occurred_at"),
        Index("payments_user_time_idx", "user_id", text("occurred_at DESC")),
        Index("payments_card_idx", "mock_card_id"),
        Index(
            "payments_one_preauth_per_reservation",
            "reservation_id",
            unique=True,
            postgresql_where=text("action = 'pre_auth'"),
        ),
        Index(
            "payments_source_event_unique",
            "source_event_id",
            unique=True,
            postgresql_where=text("source_event_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    reservation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mock_card_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mock_cards.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parent_payment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    action: Mapped[PaymentAction] = mapped_column(
        Enum(PaymentAction, name="payment_action", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    penalty_kind: Mapped[PenaltyKind | None] = mapped_column(
        Enum(PenaltyKind, name="penalty_kind", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=PaymentStatus.SUCCEEDED,
        server_default=text("'succeeded'"),
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    source_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    def __repr__(self) -> str:
        return f"<Payment {self.action.value} {self.amount_cents}c res={self.reservation_id}>"
