"""Backend → Pi MQTT command publishing tests.

We monkey-patch the MQTT client capture so no broker is needed; we verify
the topic, payload structure, and crucially that the bound-plate list is
included on every reservation/plate-related publish.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.utils.time import utcnow
from tests.conftest import card_body


class _FakePublisher:
    """Substitute for :class:`app.mqtt.publisher.Publisher` used in tests."""

    def __init__(self):
        self.published: list[tuple[str, dict]] = []

    def publish_reservation(self, bay_code, payload, *, qos=1):
        self.published.append((bay_code, payload))

    def publish_resync(self):
        pass


@pytest.fixture()
def fake_mqtt(app, monkeypatch):
    fake = _FakePublisher()
    monkeypatch.setattr(
        "app.services.mqtt_publisher.get_publisher",
        lambda _app: fake,
    )
    return fake


def _arrival(minutes: int) -> str:
    return (utcnow() + timedelta(minutes=minutes)).isoformat()


def _book_body(card, *, bay_code: str, in_minutes: int) -> dict:
    return {
        "bay_code": bay_code,
        "expected_arrival_time": _arrival(in_minutes),
        "card": card_body(card),
    }


def test_reserve_publishes_reservation_topic_with_bound_plates(
    client,
    auth_headers,
    fake_mqtt,
    bays,
    user_with_plates,
    card,
):
    resp = client.post(
        "/api/v1/reservations",
        json=_book_body(card, bay_code="A1", in_minutes=20),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert len(fake_mqtt.published) == 1
    bay_code, payload = fake_mqtt.published[0]
    assert bay_code == "A1"
    assert payload["action"] == "create"
    assert payload["bound_plates"] == ["ABC123", "XYZ789"]
    assert payload["user_id"] == str(user_with_plates.id)


def test_cancel_publishes_cancel_command(
    client,
    auth_headers,
    fake_mqtt,
    bays,
    user_with_plates,
    card,
):
    created = client.post(
        "/api/v1/reservations",
        json=_book_body(card, bay_code="A1", in_minutes=45),
        headers=auth_headers,
    ).get_json()
    fake_mqtt.published.clear()
    client.post(f"/api/v1/reservations/{created['id']}/cancel", headers=auth_headers)
    assert any(p[1]["action"] == "cancel" for p in fake_mqtt.published)


def test_plate_add_publishes_update_plates_during_active_reservation(
    client,
    auth_headers,
    fake_mqtt,
    bays,
    user_with_plates,
    card,
):
    client.post(
        "/api/v1/reservations",
        json=_book_body(card, bay_code="A1", in_minutes=30),
        headers=auth_headers,
    )
    fake_mqtt.published.clear()
    resp = client.post(
        "/api/v1/users/me/plates",
        json={"plate": "NEW000"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert len(fake_mqtt.published) == 1
    bay_code, payload = fake_mqtt.published[0]
    assert bay_code == "A1"
    assert payload["action"] == "update_plates"
    assert "NEW000" in payload["bound_plates"]


def test_plate_add_does_not_publish_when_no_active_reservation(
    client,
    auth_headers,
    fake_mqtt,
    user_with_plates,
):
    resp = client.post(
        "/api/v1/users/me/plates",
        json={"plate": "QQQ000"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert fake_mqtt.published == []
