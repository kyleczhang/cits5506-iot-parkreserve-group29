"""Cover the paho-mqtt wrapper without a real broker.

Strategy: instantiate :class:`MQTTClient`, then drive its `on_connect` /
`on_message` / `on_disconnect` paho callbacks directly to verify
subscription, dispatch, payload validation, and registered handlers.
"""

from __future__ import annotations

import json

import paho.mqtt.client as paho

from app.config import load_settings
from app.mqtt.client import MQTTClient


def _settings(**overrides):
    return load_settings(
        mqtt_enabled=True,
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_tls=False,
        mqtt_client_id="test-mqtt",
        **overrides,
    )


def test_publish_reservation_uses_correct_topic_and_serialises(monkeypatch):
    client = MQTTClient(_settings())
    captured: list[tuple[str, str]] = []

    class _Info:
        rc = paho.MQTT_ERR_SUCCESS

    def _publish(topic, data, *, qos=1, retain=False):
        captured.append((topic, data))
        return _Info()

    monkeypatch.setattr(client._client, "publish", _publish)

    client.publish_reservation("A1", {"action": "create", "bound_plates": ["ABC123"]})
    assert len(captured) == 1
    topic, data = captured[0]
    assert topic == "cloud/bay/A1/reservation"
    assert json.loads(data) == {"action": "create", "bound_plates": ["ABC123"]}


def test_publish_resync_targets_system_resync(monkeypatch):
    client = MQTTClient(_settings())
    captured: list[str] = []

    class _Info:
        rc = paho.MQTT_ERR_SUCCESS

    def _publish(topic, data, *, qos=1, retain=False):
        captured.append(topic)
        return _Info()

    monkeypatch.setattr(client._client, "publish", _publish)
    client.publish_resync()
    assert captured == ["cloud/system/resync"]


def test_publish_failure_logs_warning_but_does_not_raise(monkeypatch):
    """Use a local logging.Handler — caplog/root-logger handlers are
    reconfigured by alembic's fileConfig() if test order interleaves them."""
    import logging as _logging

    client = MQTTClient(_settings())

    class _Info:
        rc = 1  # any non-success rc

    monkeypatch.setattr(client._client, "publish", lambda *a, **kw: _Info())

    captured: list[_logging.LogRecord] = []

    class _CaptureHandler(_logging.Handler):
        def emit(self, record):
            captured.append(record)

    target_logger = _logging.getLogger("app.mqtt.client")
    target_logger.disabled = False  # alembic.fileConfig may have disabled it
    handler = _CaptureHandler()
    target_logger.addHandler(handler)
    target_logger.setLevel("WARNING")
    try:
        client.publish_reservation("A1", {"x": 1})
    finally:
        target_logger.removeHandler(handler)
    assert any("publish_failed" in r.getMessage() for r in captured)


def test_on_connect_subscribes_default_topics(monkeypatch):
    client = MQTTClient(_settings())
    subs: list[str] = []
    monkeypatch.setattr(client._client, "subscribe", lambda topic, qos=1: subs.append(topic))
    monkeypatch.setattr(client._client, "publish", lambda *a, **kw: type("X", (), {"rc": 0})())

    client._on_connect(client._client, None, None, 0)
    assert "cloud/bay/+/state" in subs
    assert "cloud/bay/+/event" in subs
    assert "cloud/system/heartbeat" in subs


def test_on_connect_failure_does_not_subscribe(monkeypatch):
    client = MQTTClient(_settings())
    subs: list[str] = []
    monkeypatch.setattr(client._client, "subscribe", lambda *a, **kw: subs.append(1))
    client._on_connect(client._client, None, None, 5)
    assert subs == []


def test_on_disconnect_clears_connected_event():
    client = MQTTClient(_settings())
    client._connected.set()
    client._on_disconnect(client._client, None, None, 0)
    assert not client._connected.is_set()


def test_on_message_routes_state_topic_to_handler():
    client = MQTTClient(_settings())
    seen: list[tuple[str, str, dict]] = []

    def state_handler(kind, code, payload):
        seen.append((kind, code, payload))

    client.on_state(state_handler)

    msg = type(
        "M",
        (),
        {
            "topic": "cloud/bay/A1/state",
            "payload": json.dumps({"foo": "bar"}).encode(),
        },
    )()
    client._on_message(client._client, None, msg)
    assert seen == [("state", "A1", {"foo": "bar"})]


def test_on_message_routes_event_topic_to_handler():
    client = MQTTClient(_settings())
    seen: list[tuple[str, str, dict]] = []
    client.on_event(lambda kind, code, payload: seen.append((kind, code, payload)))

    msg = type(
        "M",
        (),
        {"topic": "cloud/bay/A2/event", "payload": json.dumps({"event": "x"}).encode()},
    )()
    client._on_message(client._client, None, msg)
    assert seen == [("event", "A2", {"event": "x"})]


def test_on_message_routes_heartbeat():
    client = MQTTClient(_settings())
    seen: list[dict] = []
    client.on_heartbeat(lambda kind, code, payload: seen.append(payload))

    msg = type(
        "M",
        (),
        {"topic": "cloud/system/heartbeat", "payload": json.dumps({"pi_id": "x"}).encode()},
    )()
    client._on_message(client._client, None, msg)
    assert seen == [{"pi_id": "x"}]


def test_on_message_invalid_json_dropped():
    import logging as _logging

    client = MQTTClient(_settings())
    msg = type(
        "M",
        (),
        {"topic": "cloud/bay/A1/state", "payload": b"\xff\xfe not json"},
    )()

    captured: list[_logging.LogRecord] = []

    class _CaptureHandler(_logging.Handler):
        def emit(self, record):
            captured.append(record)

    target_logger = _logging.getLogger("app.mqtt.client")
    target_logger.disabled = False  # alembic.fileConfig may have disabled it
    handler = _CaptureHandler()
    target_logger.addHandler(handler)
    target_logger.setLevel("WARNING")
    try:
        client._on_message(client._client, None, msg)
    finally:
        target_logger.removeHandler(handler)
    assert any("invalid_payload" in r.getMessage() for r in captured)


def test_on_message_unknown_topic_falls_through_to_custom_handler():
    client = MQTTClient(_settings())
    seen = []
    client.register("cloud/custom/+", lambda topic, _, payload: seen.append((topic, payload)))
    msg = type(
        "M",
        (),
        {"topic": "cloud/custom/foo", "payload": json.dumps({"v": 1}).encode()},
    )()
    client._on_message(client._client, None, msg)
    assert seen == [("cloud/custom/foo", {"v": 1})]


def test_register_subscribes_when_connected(monkeypatch):
    client = MQTTClient(_settings())
    subs: list[str] = []
    monkeypatch.setattr(client._client, "subscribe", lambda topic, qos=1: subs.append(topic))
    client._connected.set()
    client.register("cloud/foo/+", lambda *a: None)
    assert subs == ["cloud/foo/+"]
