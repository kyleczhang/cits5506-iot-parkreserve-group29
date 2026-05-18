"""Licence-plate management endpoints for the current authenticated user."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.schemas.plate import PlateAddRequest, PlateOut
from app.services import auth_service, plate_service
from app.utils.errors import ValidationError as APIValidationError

bp = Blueprint("plates", __name__)


def _serialize(plate) -> dict:
    return PlateOut(
        id=str(plate.id),
        plate=plate.plate,
        label=plate.label,
        created_at=plate.created_at,
    ).model_dump(mode="json")


@bp.get("")
@jwt_required()
def list_plates():
    user = auth_service.get_by_id(get_jwt_identity())
    return jsonify([_serialize(p) for p in plate_service.list_for_user(user)])


@bp.post("")
@jwt_required()
def add_plate():
    try:
        body = PlateAddRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        raise APIValidationError(
            "invalid plate payload",
            details={
                "errors": err.errors(include_url=False, include_context=False, include_input=False)
            },
        )
    user = auth_service.get_by_id(get_jwt_identity())
    plate = plate_service.add(user=user, plate=body.plate, label=body.label)
    return jsonify(_serialize(plate)), 201


@bp.delete("/<plate>")
@jwt_required()
def remove_plate(plate: str):
    user = auth_service.get_by_id(get_jwt_identity())
    plate_service.remove(user=user, plate=plate)
    # Return 200 + empty JSON rather than 204: eventlet's WSGI server
    # forces Transfer-Encoding: chunked on 204 responses regardless of
    # explicit Content-Length, which is illegal per RFC 7230 §3.3.1 and
    # makes Vite's dev-proxy synthesise a 500 in the browser.
    return jsonify({}), 200
