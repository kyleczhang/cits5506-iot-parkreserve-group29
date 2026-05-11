"""Blueprint registration for the ParkReserve HTTP API."""

from __future__ import annotations

from flask import Flask

from app.api.auth import bp as auth_bp
from app.api.bays import bp as bays_bp
from app.api.conflicts import bp as conflicts_bp
from app.api.conflicts import internal_bp as internal_conflicts_bp
from app.api.health import bp as health_bp
from app.api.payments import bp as payments_bp
from app.api.plates import bp as plates_bp
from app.api.reservations import bp as reservations_bp


def register_blueprints(app: Flask) -> None:
    """Attach all public and internal API blueprints to ``app``."""

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(bays_bp, url_prefix="/api/v1/bays")
    app.register_blueprint(plates_bp, url_prefix="/api/v1/users/me/plates")
    app.register_blueprint(reservations_bp, url_prefix="/api/v1/reservations")
    app.register_blueprint(payments_bp, url_prefix="/api/v1/users/me/payments")
    app.register_blueprint(conflicts_bp, url_prefix="/api/v1/conflicts")
    app.register_blueprint(internal_conflicts_bp, url_prefix="/api/v1/internal")
