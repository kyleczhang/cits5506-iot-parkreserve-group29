"""Reservation lifecycle endpoints for booking, lookup, cancel, and check-in."""

from __future__ import annotations

from uuid import UUID

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.models import CheckInMechanism
from app.schemas.reservation import (
    ReservationCheckInRequest,
    ReservationCreateRequest,
    ReservationDepositInfo,
    ReservationOut,
)
from app.services import auth_service, reservation_service
from app.utils.errors import NotFoundError
from app.utils.errors import ValidationError as APIValidationError

bp = Blueprint("reservations", __name__)


def _serialize(res, *, deposit_cents: int | None = None) -> dict:
    return ReservationOut(
        id=str(res.id),
        bay_code=res.bay.code,
        user_id=str(res.user_id),
        status=res.status.value,
        expected_arrival_time=res.expected_arrival_time,
        booked_at=res.booked_at,
        check_in_grace_expires_at=res.check_in_grace_expires_at,
        checked_in_at=res.checked_in_at,
        check_in_mechanism=(
            res.check_in_mechanism.value if res.check_in_mechanism is not None else None
        ),
        cancelled_at=res.cancelled_at,
        completed_at=res.completed_at,
        payment=ReservationDepositInfo(deposit_cents=deposit_cents)
        if deposit_cents is not None
        else None,
    ).model_dump(mode="json")


def _uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError as err:
        raise NotFoundError("reservation not found", code="reservation_not_found") from err


@bp.post("")
@jwt_required()
def create_reservation():
    try:
        payload = ReservationCreateRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        raise APIValidationError(
            "invalid reservation payload",
            details={
                "errors": err.errors(include_url=False, include_context=False, include_input=False)
            },
        )
    user = auth_service.get_by_id(get_jwt_identity())
    res, deposit_cents = reservation_service.create(
        user=user,
        bay_code=payload.bay_code,
        expected_arrival_time=payload.expected_arrival_time,
        card=payload.card,
    )
    return jsonify(_serialize(res, deposit_cents=deposit_cents)), 201


@bp.get("")
@jwt_required()
def list_reservations():
    user = auth_service.get_by_id(get_jwt_identity())
    return jsonify([_serialize(r) for r in reservation_service.list_for_user(user)])


@bp.get("/<reservation_id>")
@jwt_required()
def get_reservation(reservation_id: str):
    user = auth_service.get_by_id(get_jwt_identity())
    res = reservation_service.get_by_id(_uuid(reservation_id))
    if res.user_id != user.id and user.role.value != "admin":
        raise NotFoundError("reservation not found", code="reservation_not_found")
    return jsonify(_serialize(res))


@bp.post("/<reservation_id>/cancel")
@jwt_required()
def cancel_reservation(reservation_id: str):
    user = auth_service.get_by_id(get_jwt_identity())
    res = reservation_service.cancel(user=user, reservation_id=_uuid(reservation_id))
    return jsonify(_serialize(res))


@bp.post("/<reservation_id>/check-in")
@jwt_required()
def check_in_reservation(reservation_id: str):
    try:
        body = ReservationCheckInRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        raise APIValidationError(
            "invalid check-in payload",
            details={
                "errors": err.errors(include_url=False, include_context=False, include_input=False)
            },
        )
    user = auth_service.get_by_id(get_jwt_identity())
    res = reservation_service.check_in(
        user=user,
        reservation_id=_uuid(reservation_id),
        bay_code=body.bay_code,
        source=CheckInMechanism(body.source),
    )
    return jsonify(_serialize(res))
