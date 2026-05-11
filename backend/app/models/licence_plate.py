"""Persisted licence plates bound to a user account."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    DDL,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


PLATE_FORMAT_REGEX = r"^[A-Z0-9]{1,10}$"
MAX_PLATES_PER_USER = 5


class LicencePlate(db.Model):
    """One normalised licence plate owned by a single user account."""

    __tablename__ = "licence_plates"
    __table_args__ = (
        UniqueConstraint("user_id", "plate", name="licence_plates_user_plate_unique"),
        CheckConstraint(
            f"plate ~ '{PLATE_FORMAT_REGEX}'",
            name="licence_plates_format",
        ),
        Index("licence_plates_user_idx", "user_id"),
        Index("licence_plates_plate_idx", "plate"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    plate: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    user: Mapped[User] = relationship("User", back_populates="plates")

    def __repr__(self) -> str:
        return f"<LicencePlate {self.plate} user={self.user_id}>"


# ---------------------------------------------------------------------------
# Per-user plate cap (5) — implemented as a row-level trigger because a plain
# CHECK constraint cannot reference aggregates. The same DDL is emitted by
# alembic in production migrations; this event hook makes it apply when tests
# build the schema via Base.metadata.create_all() instead of alembic.
# ---------------------------------------------------------------------------

_PLATE_CAP_FN = DDL(
    """
    CREATE OR REPLACE FUNCTION licence_plates_max_per_user()
    RETURNS TRIGGER LANGUAGE plpgsql AS $$
    BEGIN
        IF (SELECT COUNT(*) FROM licence_plates WHERE user_id = NEW.user_id) >= 5 THEN
            RAISE EXCEPTION 'plate_limit_exceeded'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END $$;
    """
)

_PLATE_CAP_TRIGGER = DDL(
    """
    DROP TRIGGER IF EXISTS licence_plates_max_per_user_tg ON licence_plates;
    CREATE TRIGGER licence_plates_max_per_user_tg
    BEFORE INSERT ON licence_plates
    FOR EACH ROW EXECUTE FUNCTION licence_plates_max_per_user();
    """
)

event.listen(
    LicencePlate.__table__,
    "after_create",
    _PLATE_CAP_FN.execute_if(dialect="postgresql"),
)
event.listen(
    LicencePlate.__table__,
    "after_create",
    _PLATE_CAP_TRIGGER.execute_if(dialect="postgresql"),
)
