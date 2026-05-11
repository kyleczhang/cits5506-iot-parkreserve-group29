"""Historical ultrasonic sensor readings reported by a parking bay device."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class SensorReading(db.Model):
    """Time-series record of one occupancy reading received from a bay sensor."""

    __tablename__ = "sensor_readings"
    __table_args__ = (Index("sensor_readings_bay_time_idx", "bay_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bay_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parking_bays.id", ondelete="CASCADE"), nullable=False
    )
    distance_cm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    occupied: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
