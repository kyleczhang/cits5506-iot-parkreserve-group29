"""Per-account licence-plate management.

Each user binds 1–5 plates. Reservations are not pinned to a specific plate —
*any* currently bound plate counts as a match. The Pi receives the user's
full bound list over MQTT each time the list changes (reservation create or
plate add/remove during an active reservation).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    OPEN_STATUSES,
    BayEventKind,
    LicencePlate,
    Reservation,
    User,
)
from app.services import event_service
from app.services.notification_service import push_plate_updated
from app.utils import plate as plate_utils
from app.utils.errors import ConflictError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def list_for_user(user: User) -> list[LicencePlate]:
    return list(
        db.session.execute(
            select(LicencePlate)
            .where(LicencePlate.user_id == user.id)
            .order_by(LicencePlate.created_at)
        ).scalars()
    )


def list_plate_strings(user_id: UUID) -> list[str]:
    rows = db.session.execute(
        select(LicencePlate.plate)
        .where(LicencePlate.user_id == user_id)
        .order_by(LicencePlate.created_at)
    ).all()
    return [r[0] for r in rows]


def add(*, user: User, plate: str, label: str | None = None) -> LicencePlate:
    normalised = plate_utils.normalise(plate)
    if not plate_utils.is_valid(normalised):
        raise ValidationError(
            "plate must be 1–10 alphanumeric characters",
            code="invalid_plate_format",
        )

    row = LicencePlate(user_id=user.id, plate=normalised, label=label)
    db.session.add(row)
    try:
        db.session.flush()
    except IntegrityError as err:
        db.session.rollback()
        msg = str(err.orig) if err.orig else str(err)
        if "plate_limit_exceeded" in msg:
            raise ValidationError(
                "this account already has the maximum 5 bound plates",
                code="plate_limit_exceeded",
            ) from err
        if "licence_plates_user_plate_unique" in msg:
            raise ConflictError(
                f"plate {normalised!r} is already bound to this account",
                code="plate_already_bound",
            ) from err
        raise

    _publish_plate_update(user)
    db.session.commit()

    push_plate_updated(user, list_for_user(user))
    return row


def remove(*, user: User, plate: str) -> None:
    normalised = plate_utils.normalise(plate)
    row = db.session.execute(
        select(LicencePlate).where(
            LicencePlate.user_id == user.id, LicencePlate.plate == normalised
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            f"plate {normalised!r} is not bound to this account",
            code="plate_not_found",
        )
    db.session.delete(row)
    db.session.flush()

    _publish_plate_update(user)
    db.session.commit()

    push_plate_updated(user, list_for_user(user))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _publish_plate_update(user: User) -> None:
    """If the user has any open reservation, re-publish the bound list to the
    Pi so its LPR matcher uses the freshest set.
    Each affected reservation also gets a `plates_updated` audit row.
    """
    open_reservations = list(
        db.session.execute(
            select(Reservation).where(
                Reservation.user_id == user.id,
                Reservation.status.in_(list(OPEN_STATUSES)),
            )
        ).scalars()
    )
    if not open_reservations:
        return

    plates = list_plate_strings(user.id)
    from app.services.mqtt_publisher import publish_reservation_command

    for reservation in open_reservations:
        publish_reservation_command(
            bay_code=reservation.bay.code,
            action="update_plates",
            reservation=reservation,
            user=user,
            bound_plates=plates,
        )
        event_service.record(
            bay_id=reservation.bay_id,
            kind=BayEventKind.PLATES_UPDATED,
            reservation_id=reservation.id,
            payload={"bound_plates": plates},
        )
