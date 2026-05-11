"""GET /api/v1/users/me/payments endpoint tests."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.utils.time import utcnow
from tests.conftest import card_body


def _arrival(minutes: int) -> str:
    return (utcnow() + timedelta(minutes=minutes)).isoformat()


def _book(client, headers, card, *, in_minutes: int):
    return client.post(
        "/api/v1/reservations",
        json={
            "bay_code": "A1",
            "expected_arrival_time": _arrival(in_minutes),
            "card": card_body(card),
        },
        headers=headers,
    )


def test_list_payments_empty(client, auth_headers, user_with_plates):
    resp = client.get("/api/v1/users/me/payments", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == {"transactions": []}


def test_list_payments_after_booking(client, auth_headers, user_with_plates, bays, card):
    _book(client, auth_headers, card, in_minutes=20)
    resp = client.get("/api/v1/users/me/payments", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["transactions"]) == 1
    tx = body["transactions"][0]
    assert tx["action"] == "pre_auth"
    assert tx["amount_cents"] == 1000
    assert tx["status"] == "succeeded"
    assert tx["penalty_kind"] is None


def test_list_payments_after_late_cancel(
    client,
    auth_headers,
    user_with_plates,
    bays,
    card,
):
    created = _book(client, auth_headers, card, in_minutes=5).get_json()
    client.post(f"/api/v1/reservations/{created['id']}/cancel", headers=auth_headers)
    body = client.get("/api/v1/users/me/payments", headers=auth_headers).get_json()
    actions = sorted(t["action"] for t in body["transactions"])
    assert actions == ["penalty_capture", "pre_auth", "release"]


def test_get_payment_detail(client, auth_headers, user_with_plates, bays, card):
    _book(client, auth_headers, card, in_minutes=20)
    listing = client.get("/api/v1/users/me/payments", headers=auth_headers).get_json()
    pid = listing["transactions"][0]["id"]
    resp = client.get(f"/api/v1/users/me/payments/{pid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == pid


def test_get_payment_404_for_nonexistent(client, auth_headers, user_with_plates):
    resp = client.get(
        f"/api/v1/users/me/payments/{uuid4()}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_get_payment_404_for_other_user(
    client,
    auth_headers,
    user_with_plates,
    bays,
    card,
):
    _book(client, auth_headers, card, in_minutes=20)
    listing = client.get("/api/v1/users/me/payments", headers=auth_headers).get_json()
    pid = listing["transactions"][0]["id"]

    # Different driver
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@test.local", "name": "Other", "password": "secret123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "other@test.local", "password": "secret123"},
    ).get_json()
    other = {"Authorization": f"Bearer {login['access_token']}"}
    resp = client.get(f"/api/v1/users/me/payments/{pid}", headers=other)
    assert resp.status_code == 404
