"""Authentication endpoints for registration, login, and current-user lookup."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services import auth_service
from app.utils.errors import ValidationError as APIValidationError

bp = Blueprint("auth", __name__)


def _serialize(user) -> dict:
    return UserOut(
        id=str(user.id), email=str(user.email), name=user.name, role=user.role.value
    ).model_dump()


@bp.post("/register")
def register():
    try:
        payload = RegisterRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        raise APIValidationError(
            "invalid register payload",
            details={
                "errors": err.errors(include_url=False, include_context=False, include_input=False)
            },
        )
    user = auth_service.register(email=payload.email, name=payload.name, password=payload.password)
    return jsonify(_serialize(user)), 201


@bp.post("/login")
def login():
    try:
        payload = LoginRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        raise APIValidationError(
            "invalid login payload",
            details={
                "errors": err.errors(include_url=False, include_context=False, include_input=False)
            },
        )
    user, token = auth_service.login(email=payload.email, password=payload.password)
    return jsonify(TokenResponse(access_token=token, user=UserOut(**_serialize(user))).model_dump())


@bp.get("/me")
@jwt_required()
def me():
    from flask_jwt_extended import get_jwt_identity

    user = auth_service.get_by_id(get_jwt_identity())
    return jsonify(_serialize(user))
