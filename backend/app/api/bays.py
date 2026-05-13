"""Public bay-status endpoints plus admin access to bay event history."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.schemas.bay import BayEventOut, BayOut
from app.services import auth_service, bay_event_service, bay_service
from app.utils.errors import ForbiddenError
from app.utils.errors import ValidationError as APIValidationError

bp = Blueprint("bays", __name__)


def _serialize(bay) -> dict:
    current = bay.current_reservation
    return BayOut(
        code=bay.code,
        label=bay.label,
        state=bay.public_state().value,
        mirror_state=bay.state.value,
        last_distance_cm=bay.last_distance_cm,
        sensor_last_seen_at=bay.sensor_last_seen_at,
        current_reservation_id=str(current.id) if current else None,
        current_reservation_arrival=current.expected_arrival_time if current else None,
        check_in_grace_expires_at=(current.check_in_grace_expires_at if current else None),
    ).model_dump(mode="json")


def _serialize_event(event) -> dict:
    return BayEventOut(
        id=event.id,
        kind=event.kind.value,
        from_state=event.from_state.value if event.from_state else None,
        to_state=event.to_state.value if event.to_state else None,
        reservation_id=str(event.reservation_id) if event.reservation_id else None,
        payload=event.payload,
        created_at=event.created_at,
    ).model_dump(mode="json")


@bp.get("")
def list_bays():
    bays = bay_service.list_all()
    return jsonify([_serialize(b) for b in bays])


@bp.get("/<code>")
def get_bay(code: str):
    bay = bay_service.get_by_code(code)
    return jsonify(_serialize(bay))


@bp.get("/<code>/events")
@jwt_required()
def list_bay_events(code: str):
    user = auth_service.get_by_id(get_jwt_identity())
    if user.role.value != "admin":
        raise ForbiddenError("admin only", code="forbidden")

    limit = request.args.get("limit", default=bay_event_service.DEFAULT_LIMIT, type=int)
    if limit is None:
        raise APIValidationError("limit must be an integer", code="invalid_query_param")

    before_raw = request.args.get("before")
    before: datetime | None = None
    if before_raw:
        try:
            before = datetime.fromisoformat(before_raw.replace("Z", "+00:00"))
        except ValueError as err:
            raise APIValidationError(
                "before must be an ISO-8601 datetime",
                code="invalid_query_param",
            ) from err

    events = bay_event_service.list_for_bay(code, limit=limit, before=before)
    return jsonify([_serialize_event(e) for e in events])
