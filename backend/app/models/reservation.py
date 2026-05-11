"""Reservation model and enums for the paid parking booking flow."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.bay import ParkingBay
    from app.models.user import User


class ReservationStatus(str, enum.Enum):
    """Lifecycle states for a reservation mirrored between backend and Pi."""

    ACTIVE = "active"  # reserved, user not yet arrived
    PENDING_CHECK_IN = "pending_check_in"  # Pi reports vehicle; awaiting auto/manual check-in
    CHECKED_IN = "checked_in"  # auto via LPR, or manual QR / button
    COMPLETED = "completed"  # vehicle drove off after check-in
    CANCELLED = "cancelled"  # cancelled ≥ 15 min before arrival (no breach)
    CANCELLED_LATE = "cancelled_late"  # cancelled < 15 min before arrival (+breach)
    EXPIRED_NO_SHOW = "expired_no_show"  # arrival + 5 min, bay still empty (+breach)
    IN_CONFLICT = "in_conflict"  # strong (no breach) or weak (+breach); kind on conflicts row


class CheckInMechanism(str, enum.Enum):
    """How a reservation was checked in once the vehicle arrived."""

    AUTO_LPR = "auto_lpr"
    QR = "qr"
    MANUAL = "manual"


OPEN_STATUSES = frozenset(
    {
        ReservationStatus.ACTIVE,
        ReservationStatus.PENDING_CHECK_IN,
        ReservationStatus.CHECKED_IN,
    }
)


class Reservation(TimestampMixin, db.Model):
    """Reservation row linking one user to one bay within a booking window."""

    __tablename__ = "reservations"
    __table_args__ = (
        # Booking window: 0 < expected_arrival - booked <= 1 hour.
        CheckConstraint(
            "expected_arrival_time > booked_at "
            "AND expected_arrival_time <= booked_at + INTERVAL '1 hour'",
            name="reservations_booking_window",
        ),
        # status='checked_in' implies checked_in_at AND check_in_mechanism populated
        CheckConstraint(
            "(status = 'checked_in' AND checked_in_at IS NOT NULL "
            "                       AND check_in_mechanism IS NOT NULL) "
            "OR status <> 'checked_in'",
            name="reservations_checked_in_has_ts",
        ),
        CheckConstraint(
            "(status IN ('cancelled', 'cancelled_late') AND cancelled_at IS NOT NULL) "
            "OR status NOT IN ('cancelled', 'cancelled_late')",
            name="reservations_cancelled_has_ts",
        ),
        # auto_lpr always carries a recognised plate; qr/manual never do.
        CheckConstraint(
            "(check_in_mechanism = 'auto_lpr' AND check_in_recognised_plate IS NOT NULL) "
            "OR (check_in_mechanism IN ('qr', 'manual') AND check_in_recognised_plate IS NULL) "
            "OR (check_in_mechanism IS NULL AND check_in_recognised_plate IS NULL)",
            name="reservations_check_in_plate_matches_mechanism",
        ),
        # At most one OPEN reservation per bay (DB-level double-book guard)
        Index(
            "reservations_one_open_per_bay",
            "bay_id",
            unique=True,
            postgresql_where=text("status IN ('active', 'pending_check_in', 'checked_in')"),
        ),
        Index("reservations_user_idx", "user_id", "booked_at"),
        Index(
            "reservations_arrival_idx",
            "expected_arrival_time",
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "reservations_check_in_grace_idx",
            "check_in_grace_expires_at",
            postgresql_where=text("status = 'pending_check_in'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    bay_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parking_bays.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(
            ReservationStatus,
            name="reservation_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ReservationStatus.ACTIVE,
        server_default=text("'active'"),
    )
    expected_arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    check_in_grace_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_in_mechanism: Mapped[CheckInMechanism | None] = mapped_column(
        Enum(
            CheckInMechanism,
            name="check_in_mechanism",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    check_in_recognised_plate: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    bay: Mapped[ParkingBay] = relationship(
        "ParkingBay",
        back_populates="reservations",
        foreign_keys=[bay_id],
    )
    user: Mapped[User] = relationship("User", back_populates="reservations")

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def __repr__(self) -> str:
        return f"<Reservation {self.id} bay={self.bay_id} {self.status.value}>"
