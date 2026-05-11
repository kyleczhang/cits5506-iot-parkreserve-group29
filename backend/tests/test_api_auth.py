"""Authentication API tests covering register, login, and current-user lookup."""

from __future__ import annotations

from flask_jwt_extended import decode_token


def test_register_and_login_flow(client, app):
    payload = {"email": "new@test.local", "name": "New User", "password": "secret123"}
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    assert resp.get_json()["email"] == "new@test.local"

    resp = client.post(
        "/api/v1/auth/login", json={"email": "new@test.local", "password": "secret123"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["access_token"]
    assert body["user"]["email"] == "new@test.local"
    with app.app_context():
        claims = decode_token(body["access_token"])
    assert claims["exp"] - claims["iat"] == 72 * 60 * 60


def test_register_duplicate_email_is_409(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "dup@test.local", "name": "d", "password": "secret123"},
    )
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "dup@test.local", "name": "d", "password": "secret123"},
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "email_taken"


def test_login_invalid_credentials_is_401(client, user):
    resp = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
    )
    assert resp.status_code == 401


def test_me_requires_jwt(client, auth_headers):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401

    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "driver@test.local"
