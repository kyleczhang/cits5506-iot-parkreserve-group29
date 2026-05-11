"""Wire inbound MQTT messages to the application's service layer.

The Pi owns the per-bay state machine; the backend mirrors its
state and reacts to derived events. Each handler runs inside a Flask app
context so SQLAlchemy / Flask-SocketIO globals work.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask
from pydantic import ValidationError

from app.mqtt.client import MQTTClient
from app.mqtt.topics import PiInboundEventPayload, StatePayload

logger = logging.getLogger(__name__)


def register_default_handlers(app: Flask, client: MQTTClient) -> None:
    def on_state(_kind: str, bay_code: str, payload: dict[str, Any]) -> None:
        try:
            parsed = StatePayload.model_validate(payload)
        except ValidationError as err:
            logger.warning("mqtt.invalid_state bay=%s err=%s", bay_code, err.errors())
            return
        from app.services.bay_service import apply_state

        with app.app_context():
            apply_state(bay_code=bay_code, payload=parsed)

    def on_event(_kind: str, bay_code: str, payload: dict[str, Any]) -> None:
        try:
            parsed = PiInboundEventPayload.model_validate(payload)
        except ValidationError as err:
            logger.warning("mqtt.invalid_event bay=%s err=%s", bay_code, err.errors())
            return
        from app.services.event_dispatcher import dispatch_event

        with app.app_context():
            dispatch_event(bay_code=bay_code, payload=parsed)

    def on_heartbeat(_kind: str, _bay_code: str, payload: dict[str, Any]) -> None:
        logger.debug("mqtt.heartbeat payload=%s", payload)

    client.on_state(on_state)
    client.on_event(on_event)
    client.on_heartbeat(on_heartbeat)
