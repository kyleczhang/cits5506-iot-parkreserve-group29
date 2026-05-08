from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.reservation import Reservation


class BayState(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"  # casual parking, no active reservation
    PENDING_CHECK_IN = "pending_check_in"  # vehicle in reserved bay; LPR running / failed
    RESERVED_CHECKED_IN = "reserved_checked_in"
    CONFLICT = "conflict"  # strong or weak conflict — kind on `conflicts` row
    OFFLINE = "offline"


class ParkingBay(TimestampMixin, db.Model):
    __tablename__ = "parking_bays"
    __table_args__ = (Index("parking_bays_state_idx", "state"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    state: Mapped[BayState] = mapped_column(
        Enum(BayState, name="bay_state", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=BayState.OFFLINE,
        server_default=text("'offline'"),
    )
    last_distance_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    sensor_last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    current_reservation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "reservations.id",
            ondelete="SET NULL",
            name="parking_bays_current_reservation_fk",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        nullable=True,
    )

    current_reservation: Mapped[Reservation | None] = relationship(
        "Reservation",
        foreign_keys=[current_reservation_id],
        post_update=True,
    )
    reservations: Mapped[list[Reservation]] = relationship(
        "Reservation",
        back_populates="bay",
        foreign_keys="Reservation.bay_id",
    )

    def __repr__(self) -> str:
        return f"<ParkingBay {self.code} {self.state.value}>"
