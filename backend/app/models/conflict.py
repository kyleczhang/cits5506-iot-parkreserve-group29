"""Conflict records for strong and weak bay-access mismatches."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class ConflictKind(str, enum.Enum):
    """Evidence strength for a bay conflict raised by the Pi."""

    STRONG = "strong"
    WEAK = "weak"


class ConflictResolution(str, enum.Enum):
    """Administrative or operational outcomes that close a conflict."""

    USER_ARRIVED_AND_CHECKED_IN = "user_arrived_and_checked_in"  # only valid for kind='weak'
    VEHICLE_LEFT = "vehicle_left"
    ADMIN_RESOLVED = "admin_resolved"
    # Holder cancelled their reservation while a strong conflict was open on
    # the bay (the wrong vehicle was still physically present). Distinct from
    # ADMIN_RESOLVED so the audit trail can tell facility action apart from a
    # victim's voluntary cancel.
    USER_CANCELLED = "user_cancelled"


class Conflict(db.Model):
    """Open or resolved conflict incident associated with a parking bay."""

    __tablename__ = "conflicts"
    __table_args__ = (
        UniqueConstraint("source_event_id", name="conflicts_source_event_unique"),
        CheckConstraint(
            "(resolved_at IS NULL AND resolution IS NULL) OR "
            "(resolved_at IS NOT NULL AND resolution IS NOT NULL)",
            name="conflicts_resolution_consistent",
        ),
        # Strong conflicts must carry the recognised plate; weak conflicts must not.
        CheckConstraint(
            "(kind = 'strong' AND recognised_plate IS NOT NULL) OR "
            "(kind = 'weak'   AND recognised_plate IS NULL "
            "                  AND evidence_image_url IS NULL)",
            name="conflicts_evidence_matches_kind",
        ),
        # Strong conflicts cannot be resolved by a user check-in.
        CheckConstraint(
            "kind <> 'strong' OR resolution IS DISTINCT FROM 'user_arrived_and_checked_in'",
            name="conflicts_strong_resolution_excludes_user_check_in",
        ),
        Index(
            "conflicts_one_open_per_bay",
            "bay_id",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
        Index(
            "conflicts_image_purge_idx",
            "image_purge_at",
            postgresql_where=text("evidence_image_url IS NOT NULL AND image_purge_at IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    bay_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parking_bays.id", ondelete="CASCADE"), nullable=False
    )
    reservation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[ConflictKind] = mapped_column(
        Enum(ConflictKind, name="conflict_kind", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    recognised_plate: Mapped[str | None] = mapped_column(String(16), nullable=True)
    lpr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    evidence_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_purge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[ConflictResolution | None] = mapped_column(
        Enum(
            ConflictResolution,
            name="conflict_resolution",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Conflict {self.id} bay={self.bay_id} kind={self.kind.value}>"
