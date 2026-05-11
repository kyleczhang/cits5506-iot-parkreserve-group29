"""Outbound MQTT publisher for reservation commands.

The backend process must be able to publish ``cloud/bay/<code>/reservation``
commands when reservations are created/cancelled/checked-in or when a
user's bound plates change. It must NOT consume inbound topics — that
is owned by :class:`app.mqtt.client.MQTTClient`.

This module exposes a :class:`Publisher` protocol so application
services depend on a small interface, plus a :class:`PahoPublisher`
implementation that owns its own paho-mqtt client. The client
deliberately has no ``on_message`` / ``on_connect``-subscribe behaviour
— a connected paho client *can* publish without subscribing.

See ``doc/backend/backend-runtime-refactor-plan.md`` §E.
"""

from __future__ import annotations

import json
import logging
import ssl
import threading
from contextlib import suppress
from typing import Protocol, runtime_checkable

import paho.mqtt.client as mqtt
from flask import Flask

from app.config import Settings
from app.mqtt.topics import reservation_topic, resync_topic

logger = logging.getLogger(__name__)

_PUBLISHER_KEY = "_parkreserve_mqtt_publisher"


@runtime_checkable
class Publisher(Protocol):
    """The outbound surface used by services. Anything implementing
    these two methods can be substituted (e.g. a no-op fake in tests)."""

    def publish_reservation(self, bay_code: str, payload: dict, *, qos: int = 1) -> None: ...

    def publish_resync(self) -> None: ...


class PahoPublisher:
    """A paho-mqtt-backed outbound-only Publisher.

    Connects asynchronously and starts the paho network loop in a
    background thread, but never subscribes to any topic and never
    registers an ``on_message`` callback.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = mqtt.Client(
            client_id=f"{settings.mqtt_client_id}-pub",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            clean_session=True,
        )
        if settings.mqtt_username:
            self._client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._connected = threading.Event()

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        logger.info(
            "publisher.connect host=%s port=%s tls=%s",
            self.settings.mqtt_host,
            self.settings.mqtt_port,
            self.settings.mqtt_tls,
        )
        self._client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=30)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        with suppress(Exception):
            self._client.disconnect()

    def wait_connected(self, timeout: float = 5.0) -> bool:
        return self._connected.wait(timeout=timeout)

    # -- publish -----------------------------------------------------------

    def publish_reservation(self, bay_code: str, payload: dict, *, qos: int = 1) -> None:
        topic = reservation_topic(self.settings.mqtt_topic_prefix, bay_code)
        self._publish(topic, payload, qos=qos)

    def publish_resync(self) -> None:
        self._publish(resync_topic(self.settings.mqtt_topic_prefix), {"request": "replay"}, qos=1)

    def _publish(self, topic: str, payload: dict, *, qos: int = 1, retain: bool = False) -> None:
        data = json.dumps(payload, default=str)
        info = self._client.publish(topic, data, qos=qos, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning("publisher.publish_failed topic=%s rc=%s", topic, info.rc)
        else:
            logger.debug("publisher.publish topic=%s payload=%s", topic, payload)

    # -- paho callbacks ----------------------------------------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if reason_code != 0:
            logger.error("publisher.connect_failed rc=%s", reason_code)
            return
        logger.info("publisher.connected")
        self._connected.set()
        # Notably: no subscribe(), no resync — those are the inbound worker's job.

    def _on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ) -> None:
        logger.warning("publisher.disconnected rc=%s", reason_code)
        self._connected.clear()


def init_publisher(app: Flask, settings: Settings) -> Publisher | None:
    """Attach a :class:`Publisher` to the Flask app.

    Returns ``None`` when MQTT is disabled — services degrade gracefully
    by skipping the publish (see ``app/services/mqtt_publisher.py``).
    """
    if not settings.mqtt_enabled:
        logger.info("publisher.disabled")
        return None
    publisher = PahoPublisher(settings)
    app.extensions[_PUBLISHER_KEY] = publisher
    publisher.start()
    return publisher


def get_publisher(app: Flask) -> Publisher | None:
    return app.extensions.get(_PUBLISHER_KEY)
