"""Publish simulated Pi-side bay state + state-machine events for every demo
bay — stands in for the Raspberry Pi + ESP32 hardware when they are
unavailable. Useful as a full demo fallback when the hardware is offline.

Drives every state and emits every event the dispatcher knows about:
  * cycles bay state available → reserved → pending_check_in → reserved_checked_in → available
  * emits `auto_check_in` (with synthetic plate match)
  * emits `conflict_strong` (with non-matching plate, plus a companion HTTPS
    POST to /api/v1/internal/conflicts/evidence carrying a fixture JPEG)
  * emits `conflict_weak`
  * emits `no_show`

Usage:
    DATABASE_URL=... python scripts/mock_pi_publisher.py --bays A1 A2 A3
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import paho.mqtt.client as mqtt

from app.config import load_settings
from app.mqtt.topics import event_topic, state_topic
from app.utils.time import utcnow

STATES = [
    "available",
    "reserved",
    "pending_check_in",
    "reserved_checked_in",
    "available",
]


def _publish(client, topic: str, payload: dict) -> None:
    client.publish(topic, json.dumps(payload, default=str), qos=1)


def _state_payload(state: str, distance_cm: float) -> dict:
    return {
        "state": state,
        "last_distance_cm": round(distance_cm, 2),
        "ts": utcnow().isoformat(),
        "event_id": str(uuid4()),
    }


def _event_payload(event: str, **extra) -> dict:
    base = {
        "event": event,
        "ts": utcnow().isoformat(),
        "event_id": str(uuid4()),
    }
    base.update({k: v for k, v in extra.items() if v is not None})
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bays", nargs="+", default=["A1", "A2", "A3"])
    parser.add_argument("--interval", type=float, default=3.0, help="seconds between ticks")
    parser.add_argument(
        "--scenario",
        choices=["cycle", "auto_check_in", "conflict_strong", "conflict_weak", "no_show"],
        default="cycle",
        help="demo scenario to drive",
    )
    parser.add_argument(
        "--plate",
        default="ABC123",
        help="LPR-recognised plate to use for auto_check_in / conflict_strong events",
    )
    args = parser.parse_args()

    settings = load_settings()
    client = mqtt.Client(
        client_id=f"mock-pi-{os.getpid()}",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
    client.loop_start()
    prefix = settings.mqtt_topic_prefix

    print(
        f"mock-pi: scenario={args.scenario} bays={args.bays} "
        f"broker={settings.mqtt_host}:{settings.mqtt_port}"
    )

    state_idx = {b: 0 for b in args.bays}
    try:
        while True:
            for bay in args.bays:
                if args.scenario == "cycle":
                    state = STATES[state_idx[bay] % len(STATES)]
                    state_idx[bay] += 1
                    distance = (
                        random.uniform(3, 10) if state != "available" else random.uniform(20, 40)
                    )
                    _publish(client, state_topic(prefix, bay), _state_payload(state, distance))

                elif args.scenario == "auto_check_in":
                    _publish(
                        client, state_topic(prefix, bay), _state_payload("pending_check_in", 5.0)
                    )
                    time.sleep(0.3)
                    _publish(
                        client,
                        event_topic(prefix, bay),
                        _event_payload(
                            "auto_check_in",
                            recognised_plate=args.plate,
                            lpr_confidence=0.95,
                        ),
                    )

                elif args.scenario == "conflict_strong":
                    _publish(
                        client, state_topic(prefix, bay), _state_payload("pending_check_in", 5.0)
                    )
                    time.sleep(0.3)
                    _publish(
                        client,
                        event_topic(prefix, bay),
                        _event_payload(
                            "conflict_strong",
                            recognised_plate=args.plate,
                            lpr_confidence=0.91,
                        ),
                    )

                elif args.scenario == "conflict_weak":
                    _publish(
                        client, state_topic(prefix, bay), _state_payload("pending_check_in", 5.0)
                    )
                    time.sleep(0.3)
                    _publish(
                        client,
                        event_topic(prefix, bay),
                        _event_payload("conflict_weak"),
                    )

                elif args.scenario == "no_show":
                    _publish(client, event_topic(prefix, bay), _event_payload("no_show"))

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
