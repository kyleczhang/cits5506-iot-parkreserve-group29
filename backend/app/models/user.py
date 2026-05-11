"""User account model for authentication and reservation ownership.

This module defines the persisted user identity used by the backend. A user
owns reservations and bound licence plates, and carries a small role enum for
authorisation decisions such as admin-only operations.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Enum, String, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.licence_plate import LicencePlate
    from app.models.reservation import Reservation


class UserRole(str, enum.Enum):
    """Application-level role assigned to a persisted user account."""

    USER = "user"
    ADMIN = "admin"


class User(TimestampMixin, db.Model):
    """User row backing authentication, authorisation, and ownership links."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserRole.USER,
        server_default=text("'user'"),
    )

    reservations: Mapped[list[Reservation]] = relationship("Reservation", back_populates="user")
    plates: Mapped[list[LicencePlate]] = relationship(
        "LicencePlate",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="LicencePlate.created_at",
    )

    def __repr__(self) -> str:
        """Return a compact debug representation keyed by email."""

        return f"<User {self.email}>"
