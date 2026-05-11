"""Conflict persistence + image-evidence retention.

The Pi state machine raises conflicts; the backend records them. Strong
conflicts carry a recognised plate + JPEG image retained for 30 days; weak
conflicts retain neither.

Image evidence travels out-of-band over HTTPS because JPEG uploads are not a
good fit for MQTT. The Pi POSTs to
``/api/v1/internal/conflicts/evidence`` after emitting ``conflict_strong``.
The MQTT handler and the upload handler may arrive in either order, so both
paths upsert the conflict row on ``source_event_id``.
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from flask import current_app
from sqlalchemy import select

from app.config import Settings
from app.extensions import db
from app.models import (
    Conflict,
    ConflictKind,
    ConflictResolution,
    ParkingBay,
)
from app.utils.errors import ConflictError, NotFoundError, ValidationError
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------


def upsert_strong(
    *,
    bay: ParkingBay,
    reservation_id: UUID | None,
    source_event_id: UUID,
    recognised_plate: str,
    lpr_confidence: float | None,
    detected_at,
) -> Conflict:
    """Find-or-create a strong-evidence conflict by ``source_event_id``.

    If a placeholder row exists from the evidence-image upload arriving first,
    we fill in the recognised-plate / detected_at fields. If the conflict is
    being created here (MQTT-event-first path), it's a fresh row.
    """
    settings: Settings = current_app.config["APP_SETTINGS"]
    purge_at = detected_at + timedelta(days=settings.evidence_retention_days)

    existing = _by_source_event(source_event_id)
    if existing is not None:
        existing.kind = ConflictKind.STRONG
        existing.recognised_plate = recognised_plate
        if lpr_confidence is not None:
            existing.lpr_confidence = Decimal(str(lpr_confidence))
        if existing.detected_at is None:
            existing.detected_at = detected_at
        if existing.image_purge_at is None and existing.evidence_image_url is not None:
            existing.image_purge_at = purge_at
        if existing.bay_id != bay.id:
            existing.bay_id = bay.id
        if reservation_id is not None and existing.reservation_id is None:
            existing.reservation_id = reservation_id
        db.session.flush()
        return existing

    row = Conflict(
        bay_id=bay.id,
        reservation_id=reservation_id,
        kind=ConflictKind.STRONG,
        recognised_plate=recognised_plate,
        lpr_confidence=Decimal(str(lpr_confidence)) if lpr_confidence is not None else None,
        source_event_id=source_event_id,
        detected_at=detected_at,
    )
    db.session.add(row)
    db.session.flush()
    return row


def upsert_weak(
    *,
    bay: ParkingBay,
    reservation_id: UUID | None,
    source_event_id: UUID,
    detected_at,
) -> Conflict:
    existing = _by_source_event(source_event_id)
    if existing is not None:
        existing.kind = ConflictKind.WEAK
        existing.recognised_plate = None
        existing.evidence_image_url = None
        existing.image_purge_at = None
        existing.lpr_confidence = None
        existing.bay_id = bay.id
        if reservation_id is not None and existing.reservation_id is None:
            existing.reservation_id = reservation_id
        db.session.flush()
        return existing

    row = Conflict(
        bay_id=bay.id,
        reservation_id=reservation_id,
        kind=ConflictKind.WEAK,
        source_event_id=source_event_id,
        detected_at=detected_at,
    )
    db.session.add(row)
    db.session.flush()
    return row


# ---------------------------------------------------------------------------
# Image evidence
# ---------------------------------------------------------------------------


def attach_evidence_image(
    *,
    bay: ParkingBay,
    source_event_id: UUID,
    image_bytes: bytes,
    recognised_plate: str | None = None,
) -> Conflict:
    """Persist a JPEG to object storage and record the URL on the conflict row.

    If the matching conflict row hasn't arrived via MQTT yet, this creates a
    placeholder ``kind='strong'`` row that the subsequent ``conflict_strong``
    event will reconcile by ``source_event_id``.
    """
    settings: Settings = current_app.config["APP_SETTINGS"]
    storage_path = Path(settings.evidence_storage_path)
    storage_path.mkdir(parents=True, exist_ok=True)

    file_id = f"{source_event_id}.jpg"
    full_path = storage_path / file_id
    full_path.write_bytes(image_bytes)
    image_url = str(full_path)

    purge_at = utcnow() + timedelta(days=settings.evidence_retention_days)

    existing = _by_source_event(source_event_id)
    if existing is None:
        # Placeholder row — recognised_plate is required by the strong CHECK
        # constraint; if the Pi hasn't sent the MQTT event yet, accept the
        # plate from the upload form.
        if not recognised_plate:
            raise ValidationError(
                "evidence upload before MQTT event must supply recognised_plate",
                code="missing_recognised_plate",
            )
        existing = Conflict(
            bay_id=bay.id,
            kind=ConflictKind.STRONG,
            recognised_plate=recognised_plate,
            source_event_id=source_event_id,
            detected_at=utcnow(),
            evidence_image_url=image_url,
            image_purge_at=purge_at,
        )
        db.session.add(existing)
    else:
        existing.evidence_image_url = image_url
        existing.image_purge_at = purge_at
        if recognised_plate and existing.recognised_plate is None:
            existing.recognised_plate = recognised_plate
    db.session.flush()
    return existing


# ---------------------------------------------------------------------------
# Resolution + listing
# ---------------------------------------------------------------------------


def resolve(
    conflict: Conflict,
    *,
    resolution: ConflictResolution,
    resolved_at=None,
) -> Conflict:
    if (
        resolution == ConflictResolution.USER_ARRIVED_AND_CHECKED_IN
        and conflict.kind == ConflictKind.STRONG
    ):
        raise ConflictError(
            "strong-evidence conflict cannot be resolved by user check-in",
            code="strong_conflict_user_resolution_invalid",
        )
    conflict.resolved_at = resolved_at or utcnow()
    conflict.resolution = resolution
    return conflict


def list_open() -> list[Conflict]:
    return list(
        db.session.execute(
            select(Conflict)
            .where(Conflict.resolved_at.is_(None))
            .order_by(Conflict.detected_at.desc())
        ).scalars()
    )


def get_by_id(conflict_id: UUID) -> Conflict:
    row = db.session.get(Conflict, conflict_id)
    if row is None:
        raise NotFoundError("conflict not found", code="conflict_not_found")
    return row


# ---------------------------------------------------------------------------
# Purge job
# ---------------------------------------------------------------------------


def purge_expired_evidence(*, now=None) -> list[UUID]:
    """Delete evidence images whose 30-day retention has elapsed.

    Returns the conflict ids whose images were purged.
    """
    now = now or utcnow()
    rows = list(
        db.session.execute(
            select(Conflict)
            .where(
                Conflict.evidence_image_url.is_not(None),
                Conflict.image_purge_at.is_not(None),
                Conflict.image_purge_at < now,
            )
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    purged: list[UUID] = []
    for row in rows:
        try:
            if row.evidence_image_url and os.path.exists(row.evidence_image_url):
                os.remove(row.evidence_image_url)
        except OSError:
            logger.exception("purge.delete_failed conflict=%s", row.id)
        row.evidence_image_url = None
        row.image_purge_at = None
        purged.append(row.id)
    if purged:
        db.session.commit()
    return purged


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _by_source_event(source_event_id: UUID) -> Conflict | None:
    return db.session.execute(
        select(Conflict).where(Conflict.source_event_id == source_event_id)
    ).scalar_one_or_none()
