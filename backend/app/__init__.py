"""Application bootstrap helpers for the ParkReserve backend.

This module centralises Flask app construction and the lifecycle management
for long-lived runtime services such as MQTT and scheduled background jobs.
Entry points can choose between creating a pure application instance for tests
and CLI use, or a fully started WSGI app for the production web process.
"""

from __future__ import annotations

import atexit
import logging
from datetime import timedelta

import structlog
from flask import Flask
from flask_cors import CORS

from app.api import register_blueprints
from app.config import Settings, load_settings
from app.extensions import db, jwt, socketio
from app.jobs.purge_evidence_images import start_purge_job
from app.jobs.reconcile_reservations import start_reconcile_job
from app.mqtt import get_mqtt_client, get_publisher, init_mqtt, init_publisher
from app.utils.errors import register_error_handlers

logger = logging.getLogger(__name__)


def _configure_logging(settings: Settings) -> None:
    """Configure stdlib and structlog output for the current environment."""
    logging.basicConfig(level=logging.INFO if settings.is_production else logging.DEBUG)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
    )


def create_app(*, settings: Settings | None = None) -> Flask:
    """Create a Flask application without starting background runtime services.

    Returns a Flask app wired with HTTP routes, Socket.IO, JWT, and the
    ORM — but *no* background work: no MQTT client, no APScheduler thread,
    no long-lived loop. This default is safe for CLI commands, tests, and
    one-off scripts; runtime entrypoints attach long-lived services later.
    """
    settings = settings or load_settings()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        JWT_SECRET_KEY=settings.jwt_secret_key,
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=settings.jwt_access_token_expires_hours),
        SQLALCHEMY_DATABASE_URI=settings.database_url,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_size": 10},
        APP_SETTINGS=settings,
        TESTING=settings.testing,
    )

    _configure_logging(settings)
    CORS(app, origins=list(settings.cors_origins), supports_credentials=True)

    db.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app, cors_allowed_origins=list(settings.cors_origins) or "*")

    # Import models so SQLAlchemy sees them even if blueprints are lazy.
    from app import models
    from app.sockets import events

    register_blueprints(app)
    register_error_handlers(app)

    return app


def start_runtime_services(app: Flask) -> None:
    """Start MQTT and scheduled jobs for a long-lived backend process.

    The function is idempotent so repeated calls from the same process do not
    duplicate MQTT connections or scheduler threads.
    """
    if app.extensions.get("_runtime_started"):
        return

    settings: Settings = app.config["APP_SETTINGS"]
    # Outbound-only MQTT publisher used to send reservation commands to bays.
    init_publisher(app, settings)
    # Inbound MQTT subscriber that consumes Pi state/event topics and requests
    # replay on connect so backend state can be reconciled.
    init_mqtt(app, settings)
    # Periodically synthesises missed reservation events such as no_show and
    # conflict_weak when Pi messages were not received.
    app.extensions["_reconcile_scheduler"] = start_reconcile_job(app)
    # Periodically removes expired strong-conflict evidence images from storage
    # while preserving the conflict rows for audit history.
    app.extensions["_purge_scheduler"] = start_purge_job(app)
    # Marks that long-lived runtime services have already been attached so
    # repeated calls do not start duplicate MQTT clients or schedulers.
    app.extensions["_runtime_started"] = True
    # Tracks whether shutdown has already run so teardown stays idempotent.
    app.extensions["_runtime_stopped"] = False

    if not app.extensions.get("_runtime_cleanup_registered"):
        # Register one process-exit cleanup so MQTT and scheduler resources are
        # shut down cleanly when this backend process exits.
        atexit.register(stop_runtime_services, app)
        app.extensions["_runtime_cleanup_registered"] = True

    logger.info("runtime.started mqtt=%s jobs=reconcile,purge", settings.mqtt_enabled)


def stop_runtime_services(app: Flask) -> None:
    """Stop runtime services previously attached to ``app``.

    Shutdown errors are logged and suppressed so process teardown can continue.
    """
    if app.extensions.get("_runtime_stopped"):
        return
    app.extensions["_runtime_stopped"] = True

    client = get_mqtt_client(app)
    if client is not None:
        try:
            client.stop()
        except Exception:
            logger.exception("runtime.stop mqtt_client")

    publisher = get_publisher(app)
    if publisher is not None and hasattr(publisher, "stop"):
        try:
            publisher.stop()
        except Exception:
            logger.exception("runtime.stop publisher")

    for key in ("_reconcile_scheduler", "_purge_scheduler"):
        scheduler = app.extensions.get(key)
        if scheduler is None:
            continue
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            logger.exception("runtime.stop scheduler=%s", key)

    logger.info("runtime.stopped")


def create_wsgi_app() -> Flask:
    """Create the production WSGI app and immediately start runtime services."""
    app = create_app()
    start_runtime_services(app)
    return app
