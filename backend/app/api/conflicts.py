"""Admin conflict view + Pi → backend image-evidence upload endpoint."""

from __future__ import annotations

from uuid import UUID

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.models import ConflictResolution
from app.schemas.conflict import ConflictOut, ConflictResolveRequest
from app.services import auth_service, conflict_service
from app.utils.errors import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.utils.errors import (
    ValidationError as APIValidationError,
)
from app.utils.time import utcnow

bp = Blueprint("conflicts", __name__)


def _serialize(conflict, *, bay_code: str | None = None) -> dict:
    code = bay_code if bay_code is not None else conflict.bay_id  # fallback
    return ConflictOut(
        id=str(conflict.id),
        bay_code=str(code),
        kind=conflict.kind.value,
        reservation_id=str(conflict.reservation_id) if conflict.reservation_id else None,
        recognised_plate=conflict.recognised_plate,
        lpr_confidence=conflict.lpr_confidence,
        evidence_image_url=conflict.evidence_image_url,
        image_purge_at=conflict.image_purge_at,
        detected_at=conflict.detected_at,
        resolved_at=conflict.resolved_at,
        resolution=conflict.resolution.value if conflict.resolution else None,
    ).model_dump(mode="json")


def _require_admin():
    user = auth_service.get_by_id(get_jwt_identity())
    if user.role.value != "admin":
        raise ForbiddenError("admin only", code="forbidden")
    return user


def _bay_code_for(conflict):
    from app.extensions import db
    from app.models import ParkingBay

    bay = db.session.get(ParkingBay, conflict.bay_id)
    return bay.code if bay else None


@bp.get("")
@jwt_required()
def list_open_conflicts():
    _require_admin()
    rows = conflict_service.list_open()
    return jsonify([_serialize(c, bay_code=_bay_code_for(c)) for c in rows])


@bp.get("/<conflict_id>/evidence")
@jwt_required()
def get_evidence(conflict_id: str):
    _require_admin()
    try:
        conflict = conflict_service.get_by_id(UUID(conflict_id))
    except (ValueError, NotFoundError) as err:
        raise NotFoundError("conflict not found", code="conflict_not_found") from err
    if not conflict.evidence_image_url:
        raise NotFoundError("evidence image purged", code="evidence_purged")
    try:
        return send_file(conflict.evidence_image_url, mimetype="image/jpeg")
    except FileNotFoundError as err:
        raise NotFoundError("evidence image purged", code="evidence_purged") from err


@bp.post("/<conflict_id>/resolve")
@jwt_required()
def resolve_conflict(conflict_id: str):
    _require_admin()
    try:
        body = ConflictResolveRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        raise APIValidationError(
            "invalid resolution payload",
            details={
                "errors": err.errors(include_url=False, include_context=False, include_input=False)
            },
        )
    try:
        conflict = conflict_service.get_by_id(UUID(conflict_id))
    except ValueError as err:
        raise NotFoundError("conflict not found", code="conflict_not_found") from err
    conflict_service.resolve(
        conflict,
        resolution=ConflictResolution(body.resolution),
    )
    from app.extensions import db
    from app.services.notification_service import push_conflict_resolved

    db.session.commit()
    push_conflict_resolved(conflict=conflict, bay=_bay_for(conflict))
    return jsonify(_serialize(conflict, bay_code=_bay_code_for(conflict)))


def _bay_for(conflict):
    from app.extensions import db
    from app.models import ParkingBay

    return db.session.get(ParkingBay, conflict.bay_id)


# ---------------------------------------------------------------------------
# Internal endpoint — Pi → backend evidence-image upload.
# Authenticated by a shared bearer token, NOT a user JWT, since the Pi has
# no user account.
# ---------------------------------------------------------------------------

internal_bp = Blueprint("internal_conflicts", __name__)


@internal_bp.post("/conflicts/evidence")
def upload_evidence():
    settings = current_app.config["APP_SETTINGS"]
    expected_token = settings.evidence_upload_token
    if expected_token:
        provided = request.headers.get("Authorization", "")
        if not provided.startswith("Bearer ") or provided[7:] != expected_token:
            raise UnauthorizedError("invalid evidence-upload token", code="unauthorized")

    bay_code = request.form.get("bay_code")
    source_event_raw = request.form.get("source_event_id")
    recognised_plate = request.form.get("recognised_plate")

    if not bay_code or not source_event_raw:
        raise APIValidationError(
            "bay_code and source_event_id are required",
            code="invalid_evidence_payload",
        )
    try:
        source_event_id = UUID(source_event_raw)
    except ValueError as err:
        raise APIValidationError(
            "source_event_id must be a UUID",
            code="invalid_evidence_payload",
        ) from err

    image = request.files.get("image")
    if image is None:
        raise APIValidationError(
            "multipart 'image' part is required",
            code="invalid_evidence_payload",
        )
    image_bytes = image.read()
    if not image_bytes:
        raise APIValidationError(
            "image payload is empty",
            code="invalid_evidence_payload",
        )

    from app.services import bay_service

    bay = bay_service.get_by_code(bay_code)
    conflict = conflict_service.attach_evidence_image(
        bay=bay,
        source_event_id=source_event_id,
        image_bytes=image_bytes,
        recognised_plate=recognised_plate,
    )
    from app.extensions import db

    db.session.commit()
    return jsonify({"conflict_id": str(conflict.id), "stored_at": utcnow().isoformat()}), 201
