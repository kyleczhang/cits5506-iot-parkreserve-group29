from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.bay import BayState


class BayEventKind(str, enum.Enum):
    STATE_CHANGED = "state_changed"
    SENSOR_ONLINE = "sensor_online"
    SENSOR_OFFLINE = "sensor_offline"
    PENDING_CHECK_IN = "pending_check_in"
    AUTO_CHECK_IN = "auto_check_in"
    CHECK_IN_CONFIRMED = "check_in_confirmed"
    CONFLICT_STRONG = "conflict_strong"
    CONFLICT_WEAK = "conflict_weak"
    CONFLICT_RESOLVED = "conflict_resolved"
    NO_SHOW = "no_show"
    RESERVATION_CREATED = "reservation_created"
    RESERVATION_CANCELLED = "reservation_cancelled"
    RESERVATION_COMPLETED = "reservation_completed"
    PLATES_UPDATED = "plates_updated"


class BayEvent(db.Model):
    __tablename__ = "bay_events"
    __table_args__ = (
        UniqueConstraint("source_event_id", name="bay_events_source_event_unique"),
        Index("bay_events_bay_time_idx", "bay_id", "created_at"),
        Index("bay_events_kind_idx", "kind"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bay_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parking_bays.id", ondelete="CASCADE"), nullable=False
    )
    reservation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[BayEventKind] = mapped_column(
        Enum(
            BayEventKind,
            name="bay_event_kind",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    from_state: Mapped[BayState | None] = mapped_column(
        Enum(
            BayState,
            name="bay_state",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    to_state: Mapped[BayState | None] = mapped_column(
        Enum(
            BayState,
            name="bay_state",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    source_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
