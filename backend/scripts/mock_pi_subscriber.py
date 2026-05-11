"""Subscribe to ``cloud/bay/+/reservation`` commands from the backend and log
them — used to verify the cloud → Pi command flow end-to-end. Particularly
useful for confirming that the bound-plate list is being published correctly
on every reservation create / plate add/remove.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import paho.mqtt.client as mqtt

from app.config import load_settings


def main() -> None:
    settings = load_settings()
    topic = f"{settings.mqtt_topic_prefix}/bay/+/reservation"
    client = mqtt.Client(
        client_id="mock-pi-sub",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    def on_message(_c, _u, msg: mqtt.MQTTMessage) -> None:
        print(f"[{msg.topic}] {msg.payload.decode()}")

    client.on_message = on_message
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
    client.subscribe(topic, qos=1)
    print(f"listening on {topic}")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
