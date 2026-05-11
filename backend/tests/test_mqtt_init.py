"""MQTT startup wiring tests for runtime service attachment."""

from __future__ import annotations

from app.config import load_settings
from app.mqtt.client import MQTTClient, get_mqtt_client, init_mqtt


def test_init_mqtt_disabled_returns_none(app):
    settings = load_settings(mqtt_enabled=False)
    assert init_mqtt(app, settings) is None
    assert get_mqtt_client(app) is None


def test_init_mqtt_enabled_attaches_client(app, monkeypatch):
    settings = load_settings(mqtt_enabled=True, mqtt_host="localhost", mqtt_port=1883)

    # Stub out the actual paho start() so we don't try to connect.
    monkeypatch.setattr(MQTTClient, "start", lambda self: None)

    client = init_mqtt(app, settings)
    assert client is not None
    assert get_mqtt_client(app) is client
