"""Pin the single-process runtime contract."""

from __future__ import annotations

from dataclasses import replace

import app as app_module
from app import create_wsgi_app, stop_runtime_services
from app.mqtt.client import MQTTClient, get_mqtt_client
from app.mqtt.publisher import PahoPublisher, get_publisher
from app.mqtt.topics import event_topic, heartbeat_topic, state_topic


class _FakeScheduler:
    def __init__(self, name: str) -> None:
        self.name = name
        self.shutdown_calls = 0

    def shutdown(self, wait: bool = False) -> None:
        self.shutdown_calls += 1


def test_create_wsgi_app_initialises_full_runtime(_settings, monkeypatch):
    """The web runtime owns publisher, subscriber, and both jobs."""
    settings = replace(_settings, mqtt_enabled=True, mqtt_host="localhost")
    monkeypatch.setattr(app_module, "load_settings", lambda **_: settings)
    monkeypatch.setattr(PahoPublisher, "start", lambda self: None)
    monkeypatch.setattr(MQTTClient, "start", lambda self: None)

    reconcile = _FakeScheduler("reconcile")
    purge = _FakeScheduler("purge")
    monkeypatch.setattr(app_module, "start_reconcile_job", lambda app: reconcile)
    monkeypatch.setattr(app_module, "start_purge_job", lambda app: purge)

    app = create_wsgi_app()

    publisher = get_publisher(app)
    assert publisher is not None
    assert isinstance(publisher, PahoPublisher)

    client = get_mqtt_client(app)
    assert client is not None
    assert isinstance(client, MQTTClient)

    assert app.extensions["_reconcile_scheduler"] is reconcile
    assert app.extensions["_purge_scheduler"] is purge


def test_stop_runtime_services_shuts_down_everything(_settings, monkeypatch):
    settings = replace(_settings, mqtt_enabled=True, mqtt_host="localhost")
    monkeypatch.setattr(app_module, "load_settings", lambda **_: settings)

    publisher_stops: list[str] = []
    mqtt_stops: list[str] = []
    monkeypatch.setattr(PahoPublisher, "start", lambda self: None)
    monkeypatch.setattr(PahoPublisher, "stop", lambda self: publisher_stops.append("publisher"))
    monkeypatch.setattr(MQTTClient, "start", lambda self: None)
    monkeypatch.setattr(MQTTClient, "stop", lambda self: mqtt_stops.append("mqtt"))

    reconcile = _FakeScheduler("reconcile")
    purge = _FakeScheduler("purge")
    monkeypatch.setattr(app_module, "start_reconcile_job", lambda app: reconcile)
    monkeypatch.setattr(app_module, "start_purge_job", lambda app: purge)

    app = create_wsgi_app()
    stop_runtime_services(app)
    stop_runtime_services(app)

    assert publisher_stops == ["publisher"]
    assert mqtt_stops == ["mqtt"]
    assert reconcile.shutdown_calls == 1
    assert purge.shutdown_calls == 1


def test_publisher_does_not_subscribe_on_connect(_settings, monkeypatch):
    """The publisher's paho client must never subscribe to any topic."""
    settings = replace(_settings, mqtt_enabled=True, mqtt_host="localhost")
    publisher = PahoPublisher(settings)

    subscribed: list[str] = []
    monkeypatch.setattr(
        publisher._client, "subscribe", lambda topic, qos=1: subscribed.append(topic)
    )
    published: list[str] = []
    monkeypatch.setattr(
        publisher._client,
        "publish",
        lambda topic, *a, **kw: published.append(topic) or _FakePublishInfo(),
    )

    publisher._on_connect(publisher._client, None, {}, 0)

    assert subscribed == [], (
        f"Publisher must not subscribe to anything on connect, got: {subscribed}"
    )
    assert all("resync" not in t for t in published)


def test_subscribing_client_does_subscribe_on_connect(_settings, monkeypatch):
    """Inbound MQTT subscribes to all topic families and asks for replay."""
    settings = replace(_settings, mqtt_enabled=True, mqtt_host="localhost")
    client = MQTTClient(settings)

    subscribed: list[str] = []
    monkeypatch.setattr(client._client, "subscribe", lambda topic, qos=1: subscribed.append(topic))
    published: list[str] = []
    monkeypatch.setattr(
        client._client,
        "publish",
        lambda topic, *a, **kw: published.append(topic) or _FakePublishInfo(),
    )

    client._on_connect(client._client, None, {}, 0)

    prefix = settings.mqtt_topic_prefix
    assert state_topic(prefix, "+") in subscribed
    assert event_topic(prefix, "+") in subscribed
    assert heartbeat_topic(prefix) in subscribed
    assert any("resync" in t for t in published)


class _FakePublishInfo:
    """Stand-in for ``paho.mqtt.client.MQTTMessageInfo``."""

    rc = 0
