"""Licence-plate API tests for listing, adding, and deleting bound plates."""

from __future__ import annotations

from app.extensions import db
from app.models import LicencePlate


def test_list_plates_for_user(client, auth_headers, user_with_plates):
    resp = client.get("/api/v1/users/me/plates", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert {row["plate"] for row in body} == {"ABC123", "XYZ789"}


def test_add_plate_normalises_case_and_strips_spaces(client, auth_headers, user, app):
    resp = client.post(
        "/api/v1/users/me/plates",
        json={"plate": "abc 999", "label": "third car"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.get_json()["plate"] == "ABC999"


def test_add_plate_rejects_bad_format(client, auth_headers, user):
    # Contains characters the regex rejects (`@`); within max_length=16 so it
    # reaches the service-layer validator instead of pydantic's length check.
    resp = client.post(
        "/api/v1/users/me/plates",
        json={"plate": "ABC@123"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "invalid_plate_format"


def test_cannot_bind_more_than_five_plates(client, auth_headers, user_with_plates):
    # user_with_plates already has 2 plates; add 3 more (total 5) successfully…
    for plate in ("AAA111", "BBB222", "CCC333"):
        resp = client.post(
            "/api/v1/users/me/plates",
            json={"plate": plate},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.get_json()
    # …the 6th must be rejected by the per-user trigger
    resp = client.post(
        "/api/v1/users/me/plates",
        json={"plate": "DDD444"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "plate_limit_exceeded"


def test_cannot_bind_same_plate_twice(client, auth_headers, user_with_plates):
    resp = client.post(
        "/api/v1/users/me/plates",
        json={"plate": "abc123"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "plate_already_bound"


def test_remove_plate(client, auth_headers, user_with_plates, app):
    resp = client.delete(
        "/api/v1/users/me/plates/ABC123",
        headers=auth_headers,
    )
    assert resp.status_code == 204
    with app.app_context():
        remaining = (
            db.session.execute(
                db.select(LicencePlate).where(LicencePlate.user_id == user_with_plates.id)
            )
            .scalars()
            .all()
        )
        assert {p.plate for p in remaining} == {"XYZ789"}


def test_remove_unknown_plate_is_404(client, auth_headers, user_with_plates):
    resp = client.delete("/api/v1/users/me/plates/NOPE", headers=auth_headers)
    assert resp.status_code == 404
