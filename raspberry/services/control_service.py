# =============================================================================
# services/control_service.py  —  Raspberry Pi Main Control Service
# =============================================================================
"""
MQTT Topic Overview
─────────────────────────────────────────────────────────────────────────────
Local (ESP32 ↔ Pi, Mosquitto):
  bay/<bay_id>/status  SUB  plain string: "available" or "occupied"
                            or JSON: {"occupied":bool,"distance_cm":float}
  bay/<code>/led       PUB  plain string: e.g. "reserved_checked_in"

  bay_id supports integers (1/2/3) or code (A1/A2/A3)

Cloud (Pi ↔ Backend, HiveMQ TLS):
  Pi → Backend:
    cloud/bay/<code>/state     PUB  StatePayload
    cloud/bay/<code>/event     PUB  EventPayload
    cloud/system/heartbeat     PUB  HeartbeatPayload (every 10s)
  Backend → Pi:
    cloud/bay/<code>/reservation  SUB  ReservationCommand
    cloud/system/resync           SUB  {"request":"replay"}

ReservationCommand.action:
  create / cancel / check_in / update_plates / release / expire_check_in
─────────────────────────────────────────────────────────────────────────────
"""

import json
import logging
import os
import re
import ssl
import threading
from datetime import datetime, timezone
from typing import Dict

import paho.mqtt.client as mqtt

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logging.warning("EasyOCR not installed, using Mock LPR (development only)")

from config.settings import (
    TEST_MODE, MOCK_PLATE, MOCK_CONFIDENCE,
    LOCAL_MQTT_HOST, LOCAL_MQTT_PORT, LOCAL_MQTT_CLIENT_ID,
    LOCAL_TOPIC_STATUS,
    CLOUD_MQTT_HOST, CLOUD_MQTT_PORT, CLOUD_MQTT_USERNAME,
    CLOUD_MQTT_PASSWORD, CLOUD_MQTT_CLIENT_ID,
    CLOUD_TOPIC_STATE, CLOUD_TOPIC_EVENT, CLOUD_TOPIC_HEARTBEAT,
    CLOUD_TOPIC_RESERVATION, CLOUD_TOPIC_RESYNC,
    IMAGE_RECEIVER_HOST, IMAGE_RECEIVER_PORT, IMAGE_UPLOAD_DIR,
    ALPR_MIN_CONFIDENCE,
    PI_NO_SHOW_TIMEOUT_SECONDS, PI_CHECKIN_WAIT_TIMEOUT_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS, PI_ID, BAY_CODES,
)
from services.state_machine import BayStateMachine, BayState, Reservation, BayEvent
from services.image_receiver import ImageReceiverService

logger = logging.getLogger(__name__)

# Bidirectional mapping between ESP32 integer bay_id and Pi internal code
BAY_ID_TO_CODE = {1: "A1", 2: "A2", 3: "A3"}
CODE_TO_BAY_ID = {"A1": 1, "A2": 2, "A3": 3}


# ── EasyOCR License Plate Recognition ────────────────────────────────────────

class LPRService:
    """EasyOCR wrapper, returns (plate|None, confidence 0-1)"""

    PLATE_PATTERN   = re.compile(r'^[A-Z0-9]{2,8}$')
    PLATE_BLACKLIST = {
        "WESTERN", "AUSTRALIA", "QUEENSLAND", "VICTORIA",
        "TASMANIA", "SYDNEY", "PERTH", "MELBOURNE",
        "SOUTHAUSTRALIA", "NEWZEALAND",
    }

    def __init__(self, min_confidence: float = 0.80):
        self.min_confidence  = min_confidence
        self.mock_plate      = MOCK_PLATE
        self.mock_confidence = MOCK_CONFIDENCE

        if TEST_MODE:
            # Test mode: force Mock, skip loading EasyOCR
            self._reader = None
            logger.info(f"[LPR] Test mode → Mock plate={self.mock_plate}, conf={self.mock_confidence}")
        elif EASYOCR_AVAILABLE:
            logger.info("[LPR] Initializing EasyOCR (first load may take ~30s)...")
            self._reader = easyocr.Reader(['en'], gpu=False)
            logger.info("[LPR] EasyOCR initialized")
        else:
            self._reader = None
            logger.warning("[LPR] EasyOCR not installed, using Mock LPR")

    def recognise(self, image_path: str):
        if not os.path.exists(image_path):
            logger.error(f"[LPR] Image not found: {image_path}")
            return None, 0.0

        if self._reader is None:
            logger.warning(f"[LPR Mock] plate={self.mock_plate}, conf={self.mock_confidence}")
            return self.mock_plate, self.mock_confidence

        try:
            results = self._reader.readtext(image_path)
            logger.info(f"[LPR] EasyOCR raw results: {[(t, round(c, 2)) for _, t, c in results]}")

            candidates = []
            for _, text, confidence in results:
                cleaned = (text.upper()
                           .replace(" ", "").replace("-", "")
                           .replace(":", "").replace(".", ""))
                if self.PLATE_PATTERN.match(cleaned) and cleaned not in self.PLATE_BLACKLIST:
                    candidates.append((cleaned, float(confidence)))

            if not candidates:
                logger.info("[LPR] No plate matching expected format found")
                return None, 0.0

            best_plate, best_conf = max(candidates, key=lambda x: x[1])
            logger.info(f"[LPR] Best result: {best_plate}, confidence: {best_conf:.2f}")
            return best_plate, best_conf

        except Exception as e:
            logger.error(f"[LPR] Recognition error: {e}")
            return None, 0.0

    def cleanup(self):
        pass


# ── Main Control Service ──────────────────────────────────────────────────────

class ControlService:

    def __init__(self):
        self._lpr = LPRService(ALPR_MIN_CONFIDENCE)

        self._bays: Dict[str, BayStateMachine] = {
            code: BayStateMachine(
                code=code,
                on_led_command=self._publish_led_command,
                on_event=self._publish_event,
                on_state_changed=self._publish_state,
                manual_checkin_grace=PI_CHECKIN_WAIT_TIMEOUT_SECONDS,
                no_show_grace=PI_NO_SHOW_TIMEOUT_SECONDS,
                alpr_min_confidence=ALPR_MIN_CONFIDENCE,
            )
            for code in BAY_CODES
        }

        # Local MQTT
        self._local_client = mqtt.Client(client_id=LOCAL_MQTT_CLIENT_ID, protocol=mqtt.MQTTv5)
        self._local_client.on_connect = self._on_local_connect
        self._local_client.on_message = self._on_local_message

        # Cloud MQTT (TLS)
        self._cloud_client = mqtt.Client(client_id=CLOUD_MQTT_CLIENT_ID, protocol=mqtt.MQTTv5)
        self._cloud_client.username_pw_set(CLOUD_MQTT_USERNAME, CLOUD_MQTT_PASSWORD)
        self._cloud_client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)
        self._cloud_client.on_connect    = self._on_cloud_connect
        self._cloud_client.on_message    = self._on_cloud_message
        self._cloud_client.on_disconnect = self._on_cloud_disconnect

        # HTTP image receiver
        self._image_receiver = ImageReceiverService(
            upload_dir=IMAGE_UPLOAD_DIR,
            on_image_received=self._on_image_received,
            on_get_status=self._get_status,
            host=IMAGE_RECEIVER_HOST,
            port=IMAGE_RECEIVER_PORT,
        )

        self._stop_event = threading.Event()

    # ── Start / Stop ──────────────────────────────────────────────────────────

    def start(self):
        logger.info("=== ControlService starting ===")
        self._image_receiver.run()
        self._local_client.connect(LOCAL_MQTT_HOST, LOCAL_MQTT_PORT, keepalive=60)
        self._local_client.loop_start()
        self._cloud_client.connect(CLOUD_MQTT_HOST, CLOUD_MQTT_PORT, keepalive=60)
        self._cloud_client.loop_start()
        threading.Thread(target=self._heartbeat_loop, daemon=True, name="heartbeat").start()
        logger.info("=== ControlService running ===")

    def stop(self):
        self._stop_event.set()
        self._local_client.loop_stop()
        self._cloud_client.loop_stop()
        self._lpr.cleanup()
        logger.info("=== ControlService stopped ===")

    def _get_status(self) -> dict:
        return {"bays": {code: sm.get_snapshot() for code, sm in self._bays.items()}}

    # ── Local MQTT: receive ESP32 sensor data ─────────────────────────────────

    def _on_local_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("[LocalMQTT] Connected")
            client.subscribe("bay/+/status", qos=1)
        else:
            logger.error(f"[LocalMQTT] Connection failed rc={rc}")

    def _on_local_message(self, client, userdata, msg):
        """
        Topic: bay/<bay_id>/status
        Payload supports two formats:
          plain string: "occupied" / "available"
          JSON: {"occupied": true, "distance_cm": 12.5}
        """
        parts = msg.topic.split("/")
        if len(parts) != 3:
            return

        # Parse bay_id → code (supports both integer and A1 formats)
        raw = parts[1]
        if raw in self._bays:
            code = raw
        else:
            try:
                code = BAY_ID_TO_CODE.get(int(raw))
            except ValueError:
                code = None
        if not code or code not in self._bays:
            logger.warning(f"[LocalMQTT] Unknown bay: {raw}")
            return

        # Parse payload (compatible with plain string and JSON)
        payload_str = msg.payload.decode().strip()
        try:
            data        = json.loads(payload_str)
            occupied    = bool(data.get("occupied", False))
            distance_cm = float(data.get("distance_cm", 0.0))
        except (json.JSONDecodeError, AttributeError):
            occupied    = (payload_str == "occupied")
            distance_cm = 0.0

        logger.debug(f"[LocalMQTT] {raw}({code}) → occupied={occupied}")
        self._bays[code].on_sensor_update(occupied, distance_cm)

    # ── Local MQTT: publish LED command to ESP32 ──────────────────────────────

    def _publish_led_command(self, code: str, command: str):
        """Topic: bay/<code>/led, payload: plain string e.g. 'reserved_checked_in'"""
        if command is None:
            return
        topic = f"bay/{code}/led"
        self._local_client.publish(topic, command, qos=1)
        logger.info(f"[LocalMQTT] → {topic}  '{command}'")

    # ── Cloud MQTT: receive Backend messages ──────────────────────────────────

    def _on_cloud_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("[CloudMQTT] Connected")
            client.subscribe(CLOUD_TOPIC_RESERVATION, qos=1)
            client.subscribe(CLOUD_TOPIC_RESYNC, qos=1)
            # After connecting, actively request Backend to re-push all reservations (handles Pi restart)
            client.publish("cloud/system/resync", json.dumps({"request": "replay"}), qos=1)
            logger.info("[CloudMQTT] Resync request sent")
        else:
            logger.error(f"[CloudMQTT] Connection failed rc={rc}")

    def _on_cloud_disconnect(self, client, userdata, rc, properties=None):
        logger.warning(f"[CloudMQTT] Disconnected (rc={rc}), waiting for auto-reconnect...")

    def _on_cloud_message(self, client, userdata, msg):
        topic = msg.topic

        if topic == "cloud/system/resync":
            try:
                data = json.loads(msg.payload.decode())
                if data.get("request") != "replay":
                    logger.warning(f"[CloudMQTT] Invalid resync payload: {data}")
                    return
            except json.JSONDecodeError:
                logger.warning("[CloudMQTT] resync payload is not valid JSON")
                return
            logger.info("[CloudMQTT] Received resync request, re-reporting all states")
            for sm in self._bays.values():
                sm.replay_state()
            return

        parts = topic.split("/")
        if (len(parts) == 4 and parts[0] == "cloud"
                and parts[1] == "bay" and parts[3] == "reservation"):
            code = parts[2]
            try:
                data = json.loads(msg.payload.decode())
            except json.JSONDecodeError:
                logger.warning(f"[CloudMQTT] Invalid JSON: {msg.payload}")
                return
            self._on_reservation_command(code, data)

    def _on_reservation_command(self, code: str, data: dict):
        if code not in self._bays:
            logger.warning(f"[CloudMQTT] Unknown bay: {code}")
            return

        action = data.get("action")
        sm     = self._bays[code]

        if action == "create":
            try:
                arrival_ts = datetime.fromisoformat(data["expected_arrival_time"]).timestamp()
                reservation = Reservation(
                    reservation_id=data["reservation_id"],
                    user_id=data["user_id"],
                    bound_plates=data.get("bound_plates", []),
                    expected_arrival_time=arrival_ts,
                )
                logger.info(f"[CloudMQTT] {code} reservation created: {reservation.reservation_id}, "
                            f"plates: {reservation.bound_plates}")
                sm.on_reservation_created(reservation)
            except (KeyError, ValueError) as e:
                logger.error(f"[CloudMQTT] create data error: {e}")

        elif action == "cancel":
            logger.info(f"[CloudMQTT] {code} reservation cancelled")
            sm.on_reservation_cancelled()

        elif action == "check_in":
            logger.info(f"[CloudMQTT] {code} manual check-in")
            sm.on_manual_checkin()

        elif action == "update_plates":
            plates = data.get("bound_plates", [])
            logger.info(f"[CloudMQTT] {code} plate list updated: {plates}")
            sm.on_plates_updated(plates)

        elif action == "release":
            reason = data.get("reason", "unknown")
            logger.info(f"[CloudMQTT] {code} received release, reason: {reason}")
            sm.on_reservation_cancelled()

        elif action == "expire_check_in":
            logger.info(f"[CloudMQTT] {code} received expire_check_in")
            sm.on_reservation_cancelled()

        else:
            logger.warning(f"[CloudMQTT] Unknown action: {action}")

    # ── Cloud MQTT: publish state/event to Backend ────────────────────────────

    def _publish_state(self, code: str, payload: dict):
        topic = CLOUD_TOPIC_STATE.format(code=code)
        self._cloud_client.publish(topic, json.dumps(payload), qos=1)
        logger.info(f"[CloudMQTT] → {topic}  state={payload['state']}")

    def _publish_event(self, code: str, event: BayEvent, payload: dict):
        topic = CLOUD_TOPIC_EVENT.format(code=code)
        self._cloud_client.publish(topic, json.dumps(payload), qos=1)
        logger.info(f"[CloudMQTT] → {topic}  event={event.value}")

    # ── Heartbeat (every 10 seconds) ──────────────────────────────────────────

    def _heartbeat_loop(self):
        while not self._stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
            payload = {"pi_id": PI_ID, "ts": datetime.now(timezone.utc).isoformat()}
            self._cloud_client.publish(CLOUD_TOPIC_HEARTBEAT, json.dumps(payload), qos=0)
            logger.debug("[CloudMQTT] ♥ heartbeat")

    # ── Image received → LPR → state machine ─────────────────────────────────

    def _on_image_received(self, code: str, image_path: str):
        if code not in self._bays:
            logger.warning(f"[LPR] Unknown bay: {code}")
            return
        logger.info(f"[LPR] Starting recognition: {image_path}")
        plate, confidence = self._lpr.recognise(image_path)
        self._bays[code].on_lpr_result(plate, confidence, image_path)
