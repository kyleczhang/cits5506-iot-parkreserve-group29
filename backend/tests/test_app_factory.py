"""Pin the ``create_app`` purity contract.

``create_app`` stays side-effect free so tests and CLI commands can build
an application object without opening MQTT connections or scheduler
threads. The long-lived web runtime attaches those services later through
``create_wsgi_app``.
"""

from __future__ import annotations

from dataclasses import replace

from app import create_app
from app.mqtt.client import get_mqtt_client
from app.mqtt.publisher import get_publisher


def test_create_app_does_not_start_schedulers(_settings):
    flask_app = create_app(settings=_settings)
    assert "_reconcile_scheduler" not in flask_app.extensions
    assert "_purge_scheduler" not in flask_app.extensions


def test_create_app_does_not_initialise_mqtt_even_when_enabled(_settings):
    """The default factory must attach neither inbound nor outbound MQTT."""
    settings = replace(_settings, mqtt_enabled=True, mqtt_host="localhost")
    flask_app = create_app(settings=settings)
    assert get_mqtt_client(flask_app) is None
    assert get_publisher(flask_app) is None
