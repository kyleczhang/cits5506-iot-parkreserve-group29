"""Inbound MQTT subscriber used by the long-lived backend process.

This module owns the broker subscription loop. It is attached from the
main web runtime so Pi events can update the database and immediately
broadcast Socket.IO notifications from the same process.

Subscribes to:
  - ``cloud/bay/+/state``    (Pi-side bay-state mirror)
  - ``cloud/bay/+/event``    (Pi-side state-machine events)
  - ``cloud/system/heartbeat``

Also issues:
  - ``cloud/system/resync``  on (re)connect — internal lifecycle
    request that asks the Pi to replay state. This is *not* a
    user-facing publish surface.

Inbound messages are dispatched to user-registered handlers via
:meth:`on_state`, :meth:`on_event`, :meth:`on_heartbeat`. Application
wiring happens in :mod:`app.mqtt.handlers`.
"""

from __future__ import annotations

import json
import logging
import ssl
import threading
from collections.abc import Callable
from contextlib import suppress

import paho.mqtt.client as mqtt
from flask import Flask

from app.config import Settings
from app.mqtt.topics import (
    event_topic,
    heartbeat_topic,
    parse_event_topic,
    parse_state_topic,
    reservation_topic,
    resync_topic,
    state_topic,
)

logger = logging.getLogger(__name__)

MessageHandler = Callable[[str, str, dict], None]

_INSTANCE_KEY = "_parkreserve_mqtt_client"


class MQTTClient:
    def __init__(self, settings: Settings) -> None:
        """Create an inbound MQTT client.

        Always subscribes to ``state``/``event``/``heartbeat`` topics on
        connect and requests a resync.
        """
        self.settings = settings
        self._client = mqtt.Client(
            client_id=settings.mqtt_client_id,
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
        self._client.on_message = self._on_message

        self._handlers: dict[str, MessageHandler] = {}
        self._routers: dict[str, MessageHandler] = {}
        self._lock = threading.Lock()
        self._connected = threading.Event()

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        logger.info(
            "mqtt.connect host=%s port=%s tls=%s",
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
            logger.warning("mqtt.publish_failed topic=%s rc=%s", topic, info.rc)
        else:
            logger.debug("mqtt.publish topic=%s payload=%s", topic, payload)

    # -- subscribe ---------------------------------------------------------

    def register(self, topic_filter: str, handler: MessageHandler) -> None:
        with self._lock:
            self._handlers[topic_filter] = handler
            if self._connected.is_set():
                self._client.subscribe(topic_filter, qos=1)

    # -- paho callbacks ----------------------------------------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if reason_code != 0:
            logger.error("mqtt.connect_failed rc=%s", reason_code)
            return
        logger.info("mqtt.connected")
        self._connected.set()
        prefix = self.settings.mqtt_topic_prefix
        for topic in (
            state_topic(prefix, "+"),
            event_topic(prefix, "+"),
            heartbeat_topic(prefix),
        ):
            client.subscribe(topic, qos=1)
        with self._lock:
            for topic_filter in self._handlers:
                client.subscribe(topic_filter, qos=1)
        self.publish_resync()

    def _on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ) -> None:
        logger.warning("mqtt.disconnected rc=%s", reason_code)
        self._connected.clear()

    def _on_message(self, client, userdata, message: mqtt.MQTTMessage) -> None:
        topic = message.topic
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as err:
            logger.warning("mqtt.invalid_payload topic=%s err=%s", topic, err)
            return

        code = parse_state_topic(topic)
        if code:
            self._dispatch("state", code, payload)
            return
        code = parse_event_topic(topic)
        if code:
            self._dispatch("event", code, payload)
            return
        if topic == heartbeat_topic(self.settings.mqtt_topic_prefix):
            self._dispatch("heartbeat", "", payload)
            return

        with self._lock:
            handlers = list(self._handlers.items())
        for filt, handler in handlers:
            if mqtt.topic_matches_sub(filt, topic):
                try:
                    handler(topic, "", payload)
                except Exception:
                    logger.exception("mqtt.handler_error topic=%s", topic)

    def _dispatch(self, kind: str, bay_code: str, payload: dict) -> None:
        handler = self._routers.get(kind)
        if handler is None:
            return
        try:
            handler(kind, bay_code, payload)
        except Exception:
            logger.exception("mqtt.route_error kind=%s bay=%s", kind, bay_code)

    def on_state(self, handler: MessageHandler) -> None:
        self._routers["state"] = handler

    def on_event(self, handler: MessageHandler) -> None:
        self._routers["event"] = handler

    def on_heartbeat(self, handler: MessageHandler) -> None:
        self._routers["heartbeat"] = handler


def init_mqtt(app: Flask, settings: Settings) -> MQTTClient | None:
    """Attach an inbound MQTTClient to the Flask app.

    Returns ``None`` when MQTT is disabled.
    """
    if not settings.mqtt_enabled:
        logger.info("mqtt.disabled")
        return None
    client = MQTTClient(settings)
    app.extensions[_INSTANCE_KEY] = client
    from app.mqtt.handlers import register_default_handlers

    register_default_handlers(app, client)
    client.start()
    return client


def get_mqtt_client(app: Flask) -> MQTTClient | None:
    return app.extensions.get(_INSTANCE_KEY)
