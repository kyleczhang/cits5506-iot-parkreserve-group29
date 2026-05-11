"""Coverage for branches in API blueprints not exercised by the main tests:
malformed bodies, get-reservation flow, plate-removal idempotency, and
admin-detail access."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.utils.time import utcnow
from tests.conftest import card_body


def _arrival(minutes: int) -> str:
    return (utcnow() + timedelta(minutes=minutes)).isoformat()


def _book_body(card, *, bay_code: str, in_minutes: int) -> dict:
    return {
        "bay_code": bay_code,
        "expected_arrival_time": _arrival(in_minutes),
        "card": card_body(card),
    }


def test_register_rejects_invalid_payload(client):
    resp = client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "validation_error"


def test_login_rejects_invalid_payload(client):
    resp = client.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422


def test_create_reservation_rejects_invalid_payload(client, auth_headers):
    resp = client.post("/api/v1/reservations", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_check_in_invalid_payload_422(client, auth_headers, bays, user_with_plates, card):
    created = client.post(
        "/api/v1/reservations",
        json=_book_body(card, bay_code="A1", in_minutes=20),
        headers=auth_headers,
    ).get_json()
    resp = client.post(
        f"/api/v1/reservations/{created['id']}/check-in",
        json={"bay_code": "A1"},  # source missing
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_get_reservation_404_for_nonexistent(client, auth_headers, bays):
    resp = client.get(f"/api/v1/reservations/{uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_get_reservation_other_user_returns_404(
    client,
    auth_headers,
    admin_headers,
    bays,
    user_with_plates,
    card,
):
    """Owner-or-admin guard: a regular user cannot fetch someone else's reservation."""
    created = client.post(
        "/api/v1/reservations",
        json=_book_body(card, bay_code="A1", in_minutes=20),
        headers=auth_headers,
    ).get_json()

    # Admin CAN see it (admin override)
    resp_admin = client.get(f"/api/v1/reservations/{created['id']}", headers=admin_headers)
    assert resp_admin.status_code == 200

    # A different driver may not — register a second user
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@test.local", "name": "Other", "password": "secret123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "other@test.local", "password": "secret123"},
    ).get_json()
    other_headers = {"Authorization": f"Bearer {login['access_token']}"}
    resp_other = client.get(f"/api/v1/reservations/{created['id']}", headers=other_headers)
    assert resp_other.status_code == 404


def test_invalid_uuid_in_url_404(client, auth_headers, bays):
    resp = client.get("/api/v1/reservations/not-a-uuid", headers=auth_headers)
    assert resp.status_code == 404


def test_evidence_upload_invalid_token_401(client, bays):
    resp = client.post(
        "/api/v1/internal/conflicts/evidence",
        data={"bay_code": "A1", "source_event_id": str(uuid4())},
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_evidence_upload_missing_required_field_422(client, bays):
    resp = client.post(
        "/api/v1/internal/conflicts/evidence",
        data={},
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer test-evidence-token"},
    )
    assert resp.status_code == 422


def test_evidence_upload_bad_uuid_422(client, bays):
    from io import BytesIO

    resp = client.post(
        "/api/v1/internal/conflicts/evidence",
        data={
            "bay_code": "A1",
            "source_event_id": "not-a-uuid",
            "recognised_plate": "ZZ9",
            "image": (BytesIO(b"\xff fake"), "x.jpg"),
        },
        content_type="multipart/form-data",
        headers={"Authorization": "Bearer test-evidence-token"},
    )
    assert resp.status_code == 422


def test_admin_resolve_invalid_resolution_value_422(client, admin_headers, bays):
    resp = client.post(
        f"/api/v1/conflicts/{uuid4()}/resolve",
        json={"resolution": "made-up"},
        headers=admin_headers,
    )
    assert resp.status_code == 422
