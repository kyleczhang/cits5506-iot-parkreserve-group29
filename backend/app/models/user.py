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
    USER = "user"
    ADMIN = "admin"


class User(TimestampMixin, db.Model):
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
        return f"<User {self.email}>"
