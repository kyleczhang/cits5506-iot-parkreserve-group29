"""Health endpoints for the web process.

After Phase 4 these report only what the web process can answer for
itself — they do *not* claim to know the liveness of the inbound MQTT
worker or the scheduler process. Each of those has its own systemd
unit and journal; their health is managed by process supervision.

- ``/healthz`` — pure liveness. Returns 200 as long as this process
  can serve HTTP. No I/O.
- ``/readyz``  — readiness. Returns 200 only when the web process can
  serve real requests, which today means: database reachable.

See ``doc/backend/backend-runtime-refactor-plan.md`` §Health Check
Semantics.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import text

from app.extensions import db

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz():
    """Liveness — the process is up."""
    return jsonify({"status": "ok"})


@bp.get("/readyz")
def readyz():
    """Readiness — the web process can serve requests.

    DB is the only hard dependency for HTTP responses. Outbound MQTT
    publish is best-effort and degrades gracefully when the broker is
    down (services skip the publish but business state still mutates),
    so it is intentionally not part of readiness.
    """
    checks = {"db": False}
    try:
        db.session.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:
        pass

    return jsonify(checks), 200 if checks["db"] else 503
