"""Health-check endpoint smoke tests."""

from __future__ import annotations


def test_healthz_returns_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_readyz_reports_db_only(client):
    """After Phase 4 readiness reflects only what the web process can
    answer for itself: database reachable. MQTT publisher liveness is
    intentionally not part of readiness — outbound publish degrades
    gracefully, and worker liveness is observed via systemd."""
    resp = client.get("/readyz")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"db": True}
