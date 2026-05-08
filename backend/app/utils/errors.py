from __future__ import annotations

from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    """Base class for application-level errors that map to a JSON response."""

    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"


class ConflictError(APIError):
    status_code = 409
    code = "conflict"


class ValidationError(APIError):
    status_code = 422
    code = "validation_error"


class UnauthorizedError(APIError):
    status_code = 401
    code = "unauthorized"


class PaymentError(APIError):
    status_code = 402
    code = "payment_error"


class ForbiddenError(APIError):
    status_code = 403
    code = "forbidden"


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return jsonify(_envelope(err.code, err.message, err.details)), err.status_code

    @app.errorhandler(HTTPException)
    def handle_http(err: HTTPException):
        return jsonify(
            _envelope(err.name.lower().replace(" ", "_"), err.description or err.name)
        ), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        app.logger.exception("unhandled error: %s", err)
        return jsonify(_envelope("internal_error", "internal server error")), 500
