"""Authenticated payment-ledger endpoints for the current user."""

from __future__ import annotations

from uuid import UUID

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.schemas.payment import TransactionListResponse, TransactionOut
from app.services import auth_service, payment_service
from app.utils.errors import NotFoundError

bp = Blueprint("payments", __name__)


def _serialize(p) -> TransactionOut:
    return TransactionOut(
        id=str(p.id),
        reservation_id=str(p.reservation_id),
        action=p.action.value,
        penalty_kind=p.penalty_kind.value if p.penalty_kind is not None else None,
        amount_cents=p.amount_cents,
        status=p.status.value,
        occurred_at=p.occurred_at,
    )


def _uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError as err:
        raise NotFoundError("payment not found", code="payment_not_found") from err


@bp.get("")
@jwt_required()
def list_my_payments():
    user = auth_service.get_by_id(get_jwt_identity())
    rows = payment_service.list_for_user(user.id)
    return jsonify(
        TransactionListResponse(transactions=[_serialize(p) for p in rows]).model_dump(mode="json")
    )


@bp.get("/<payment_id>")
@jwt_required()
def get_my_payment(payment_id: str):
    user = auth_service.get_by_id(get_jwt_identity())
    p = payment_service.get_for_user(user_id=user.id, payment_id=_uuid(payment_id))
    if p is None:
        raise NotFoundError("payment not found", code="payment_not_found")
    return jsonify(_serialize(p).model_dump(mode="json"))
