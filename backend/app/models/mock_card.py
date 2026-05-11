"""Mock-bank card model used by the in-process payment simulator."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class MockCard(db.Model):
    """In-process mock-bank card.

    Seeded test data only — never accepts real card numbers.
    `balance_cents` is decremented on `pre_auth` and restored on
    `release` / `refund` (penalty captures leave it unchanged).
    """

    __tablename__ = "mock_cards"
    __table_args__ = (
        CheckConstraint("card_number ~ '^[0-9]{13,19}$'", name="mock_cards_number_format"),
        CheckConstraint("cvv ~ '^[0-9]{3,4}$'", name="mock_cards_cvv_format"),
        CheckConstraint("expiry_month BETWEEN 1 AND 12", name="mock_cards_expiry_month"),
        CheckConstraint("expiry_year BETWEEN 2024 AND 2099", name="mock_cards_expiry_year"),
        CheckConstraint("balance_cents >= 0", name="mock_cards_balance_nonneg"),
        Index("mock_cards_number_idx", "card_number"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    card_number: Mapped[str] = mapped_column(String(19), nullable=False, unique=True)
    cvv: Mapped[str] = mapped_column(String(4), nullable=False)
    holder_name: Mapped[str] = mapped_column(String(120), nullable=False)
    expiry_month: Mapped[int] = mapped_column(Integer, nullable=False)
    expiry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    def __repr__(self) -> str:
        return f"<MockCard {self.card_number[-4:]} balance={self.balance_cents}>"
