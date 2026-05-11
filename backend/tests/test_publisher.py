"""Pin :class:`PahoPublisher` and :func:`init_publisher` contracts.

The publisher is the *only* MQTT surface the web process should touch.
These tests fail loudly if a refactor accidentally bundles inbound
behaviour back into the publisher (e.g. registers an ``on_message``
callback or subscribes to anything on connect).

See ``doc/backend/backend-runtime-refactor-plan.md`` §E.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.mqtt.publisher import (
    PahoPublisher,
    Publisher,
    get_publisher,
    init_publisher,
)
from app.mqtt.topics import reservation_topic, resync_topic


@pytest.fixture()
def publisher_settings(_settings):
    return replace(_settings, mqtt_enabled=True, mqtt_host="localhost")


# ---------------------------------------------------------------------------
# init_publisher / get_publisher
# ---------------------------------------------------------------------------


def test_init_publisher_disabled_returns_none(app, _settings):
    settings = replace(_settings, mqtt_enabled=False)
    assert init_publisher(app, settings) is None
    assert get_publisher(app) is None


def test_init_publisher_enabled_attaches_publisher(app, publisher_settings, monkeypatch):
    monkeypatch.setattr(PahoPublisher, "start", lambda self: None)
    publisher = init_publisher(app, publisher_settings)
    assert publisher is not None
    assert get_publisher(app) is publisher
    assert isinstance(publisher, Publisher)  # runtime-checkable Protocol


# ---------------------------------------------------------------------------
# Outbound publishes — the actual contract callers depend on
# ---------------------------------------------------------------------------


def test_publish_reservation_emits_correct_topic_and_payload(publisher_settings, monkeypatch):
    publisher = PahoPublisher(publisher_settings)

    captured: list[tuple[str, str, int, bool]] = []

    def _fake_publish(topic, data, qos=1, retain=False):
        captured.append((topic, data, qos, retain))
        return _FakePublishInfo()

    monkeypatch.setattr(publisher._client, "publish", _fake_publish)

    payload = {"action": "create", "bound_plates": ["ABC123"]}
    publisher.publish_reservation("A1", payload, qos=1)

    assert len(captured) == 1
    topic, data, qos, retain = captured[0]
    assert topic == reservation_topic(publisher_settings.mqtt_topic_prefix, "A1")
    assert qos == 1
    assert retain is False
    assert json.loads(data) == payload


def test_publish_resync_emits_correct_topic(publisher_settings, monkeypatch):
    publisher = PahoPublisher(publisher_settings)

    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(
        publisher._client,
        "publish",
        lambda topic, data, qos=1, retain=False: (
            captured.append((topic, data)) or _FakePublishInfo()
        ),
    )

    publisher.publish_resync()

    assert len(captured) == 1
    topic, data = captured[0]
    assert topic == resync_topic(publisher_settings.mqtt_topic_prefix)
    assert json.loads(data) == {"request": "replay"}


# ---------------------------------------------------------------------------
# Negative space — what the publisher must *not* do
# ---------------------------------------------------------------------------


def test_publisher_paho_client_has_no_on_message_callback(publisher_settings):
    """If a future change wires an on_message handler onto the
    publisher's client, this test fails — protecting the invariant
    that web never consumes inbound MQTT."""
    publisher = PahoPublisher(publisher_settings)
    assert publisher._client.on_message is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakePublishInfo:
    rc = 0  # MQTT_ERR_SUCCESS
