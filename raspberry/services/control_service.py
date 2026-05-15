# =============================================================================
# services/control_service.py  —  树莓派控制逻辑主服务
# =============================================================================
"""
MQTT 话题总览
─────────────────────────────────────────────────────────────────────────────
本地（ESP32 ↔ Pi，Mosquitto）：
  bay/<bay_id>/status  SUB  纯字符串："available" 或 "occupied"
                            或 JSON：{"occupied":bool,"distance_cm":float}
  bay/<code>/led       PUB  纯字符串：如 "reserved_checked_in"

  bay_id 支持整数（1/2/3）或 code（A1/A2/A3）

云端（Pi ↔ Backend，HiveMQ TLS）：
  Pi → Backend：
    cloud/bay/<code>/state     PUB  StatePayload
    cloud/bay/<code>/event     PUB  EventPayload
    cloud/system/heartbeat     PUB  HeartbeatPayload（每10s）
  Backend → Pi：
    cloud/bay/<code>/reservation  SUB  ReservationCommand
    cloud/system/resync           SUB  {"request":"replay"}

ReservationCommand.action：
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
    logging.warning("EasyOCR 未安装，将使用 Mock LPR（仅开发用途）")

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

# ESP32 整数 bay_id ↔ Pi 内部 code 双向映射
BAY_ID_TO_CODE = {1: "A1", 2: "A2", 3: "A3"}
CODE_TO_BAY_ID = {"A1": 1, "A2": 2, "A3": 3}


# ── EasyOCR 车牌识别 ──────────────────────────────────────────────────────────

class LPRService:
    """EasyOCR 封装，返回 (plate|None, confidence 0-1)"""

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
            # 测试模式：强制使用 Mock，不加载 EasyOCR
            self._reader = None
            logger.info(f"[LPR] 测试模式 → Mock plate={self.mock_plate}, conf={self.mock_confidence}")
        elif EASYOCR_AVAILABLE:
            logger.info("[LPR] 初始化 EasyOCR（首次加载约30秒）...")
            self._reader = easyocr.Reader(['en'], gpu=False)
            logger.info("[LPR] EasyOCR 初始化完成")
        else:
            self._reader = None
            logger.warning("[LPR] EasyOCR 未安装，使用 Mock LPR")

    def recognise(self, image_path: str):
        if not os.path.exists(image_path):
            logger.error(f"[LPR] 图片不存在：{image_path}")
            return None, 0.0

        if self._reader is None:
            logger.warning(f"[LPR Mock] plate={self.mock_plate}, conf={self.mock_confidence}")
            return self.mock_plate, self.mock_confidence

        try:
            results = self._reader.readtext(image_path)
            logger.info(f"[LPR] EasyOCR 原始结果：{[(t, round(c, 2)) for _, t, c in results]}")

            candidates = []
            for _, text, confidence in results:
                cleaned = (text.upper()
                           .replace(" ", "").replace("-", "")
                           .replace(":", "").replace(".", ""))
                if self.PLATE_PATTERN.match(cleaned) and cleaned not in self.PLATE_BLACKLIST:
                    candidates.append((cleaned, float(confidence)))

            if not candidates:
                logger.info("[LPR] 未识别到符合格式的车牌")
                return None, 0.0

            best_plate, best_conf = max(candidates, key=lambda x: x[1])
            logger.info(f"[LPR] 最佳结果：{best_plate}，置信度：{best_conf:.2f}")
            return best_plate, best_conf

        except Exception as e:
            logger.error(f"[LPR] 识别异常：{e}")
            return None, 0.0

    def cleanup(self):
        pass


# ── 主控服务 ──────────────────────────────────────────────────────────────────

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

        # 本地 MQTT
        self._local_client = mqtt.Client(client_id=LOCAL_MQTT_CLIENT_ID, protocol=mqtt.MQTTv5)
        self._local_client.on_connect = self._on_local_connect
        self._local_client.on_message = self._on_local_message

        # 云端 MQTT（TLS）
        self._cloud_client = mqtt.Client(client_id=CLOUD_MQTT_CLIENT_ID, protocol=mqtt.MQTTv5)
        self._cloud_client.username_pw_set(CLOUD_MQTT_USERNAME, CLOUD_MQTT_PASSWORD)
        self._cloud_client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)
        self._cloud_client.on_connect    = self._on_cloud_connect
        self._cloud_client.on_message    = self._on_cloud_message
        self._cloud_client.on_disconnect = self._on_cloud_disconnect

        # HTTP 图片接收
        self._image_receiver = ImageReceiverService(
            upload_dir=IMAGE_UPLOAD_DIR,
            on_image_received=self._on_image_received,
            on_get_status=self._get_status,
            host=IMAGE_RECEIVER_HOST,
            port=IMAGE_RECEIVER_PORT,
        )

        self._stop_event = threading.Event()

    # ── 启动 / 停止 ───────────────────────────────────────────────────────────

    def start(self):
        logger.info("=== ControlService 启动 ===")
        self._image_receiver.run()
        self._local_client.connect(LOCAL_MQTT_HOST, LOCAL_MQTT_PORT, keepalive=60)
        self._local_client.loop_start()
        self._cloud_client.connect(CLOUD_MQTT_HOST, CLOUD_MQTT_PORT, keepalive=60)
        self._cloud_client.loop_start()
        threading.Thread(target=self._heartbeat_loop, daemon=True, name="heartbeat").start()
        logger.info("=== ControlService 运行中 ===")

    def stop(self):
        self._stop_event.set()
        self._local_client.loop_stop()
        self._cloud_client.loop_stop()
        self._lpr.cleanup()
        logger.info("=== ControlService 已停止 ===")

    def _get_status(self) -> dict:
        return {"bays": {code: sm.get_snapshot() for code, sm in self._bays.items()}}

    # ── 本地 MQTT：接收 ESP32 传感器数据 ─────────────────────────────────────

    def _on_local_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("[LocalMQTT] 连接成功")
            client.subscribe("bay/+/status", qos=1)
        else:
            logger.error(f"[LocalMQTT] 连接失败 rc={rc}")

    def _on_local_message(self, client, userdata, msg):
        """
        话题：bay/<bay_id>/status
        Payload 支持两种格式：
          纯字符串："occupied" / "available"
          JSON：{"occupied": true, "distance_cm": 12.5}
        """
        parts = msg.topic.split("/")
        if len(parts) != 3:
            return

        # 解析 bay_id → code（支持整数和 A1 两种格式）
        raw = parts[1]
        if raw in self._bays:
            code = raw
        else:
            try:
                code = BAY_ID_TO_CODE.get(int(raw))
            except ValueError:
                code = None
        if not code or code not in self._bays:
            logger.warning(f"[LocalMQTT] 未知车位：{raw}")
            return

        # 解析 payload（兼容纯字符串和 JSON）
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

    # ── 本地 MQTT：发布 LED 指令给 ESP32 ─────────────────────────────────────

    def _publish_led_command(self, code: str, command: str):
        """话题：bay/<code>/led，payload：纯字符串如 'reserved_checked_in'"""
        if command is None:
            return
        topic = f"bay/{code}/led"
        self._local_client.publish(topic, command, qos=1)
        logger.info(f"[LocalMQTT] → {topic}  '{command}'")

    # ── 云端 MQTT：接收 Backend 消息 ─────────────────────────────────────────

    def _on_cloud_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("[CloudMQTT] 连接成功")
            client.subscribe(CLOUD_TOPIC_RESERVATION, qos=1)
            client.subscribe(CLOUD_TOPIC_RESYNC, qos=1)
            # Pi 连接成功后主动请求 Backend 重新推送所有预约（处理 Pi 重启）
            client.publish("cloud/system/resync", json.dumps({"request": "replay"}), qos=1)
            logger.info("[CloudMQTT] 已发送 resync 请求")
        else:
            logger.error(f"[CloudMQTT] 连接失败 rc={rc}")

    def _on_cloud_disconnect(self, client, userdata, rc, properties=None):
        logger.warning(f"[CloudMQTT] 断开（rc={rc}），等待自动重连…")

    def _on_cloud_message(self, client, userdata, msg):
        topic = msg.topic

        if topic == "cloud/system/resync":
            try:
                data = json.loads(msg.payload.decode())
                if data.get("request") != "replay":
                    logger.warning(f"[CloudMQTT] resync payload 错误：{data}")
                    return
            except json.JSONDecodeError:
                logger.warning("[CloudMQTT] resync payload 无效 JSON")
                return
            logger.info("[CloudMQTT] 收到 resync 请求，重新上报所有状态")
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
                logger.warning(f"[CloudMQTT] 无效 JSON：{msg.payload}")
                return
            self._on_reservation_command(code, data)

    def _on_reservation_command(self, code: str, data: dict):
        if code not in self._bays:
            logger.warning(f"[CloudMQTT] 未知车位：{code}")
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
                logger.info(f"[CloudMQTT] {code} 预约创建：{reservation.reservation_id}，"
                            f"车牌：{reservation.bound_plates}")
                sm.on_reservation_created(reservation)
            except (KeyError, ValueError) as e:
                logger.error(f"[CloudMQTT] create 数据异常：{e}")

        elif action == "cancel":
            logger.info(f"[CloudMQTT] {code} 预约取消")
            sm.on_reservation_cancelled()

        elif action == "check_in":
            logger.info(f"[CloudMQTT] {code} 手动 check-in")
            sm.on_manual_checkin()

        elif action == "update_plates":
            plates = data.get("bound_plates", [])
            logger.info(f"[CloudMQTT] {code} 车牌列表更新：{plates}")
            sm.on_plates_updated(plates)

        elif action == "release":
            reason = data.get("reason", "unknown")
            logger.info(f"[CloudMQTT] {code} 收到 release，原因：{reason}")
            sm.on_reservation_cancelled()

        elif action == "expire_check_in":
            logger.info(f"[CloudMQTT] {code} 收到 expire_check_in")
            sm.on_reservation_cancelled()

        else:
            logger.warning(f"[CloudMQTT] 未知 action：{action}")

    # ── 云端 MQTT：发布状态/事件给 Backend ───────────────────────────────────

    def _publish_state(self, code: str, payload: dict):
        topic = CLOUD_TOPIC_STATE.format(code=code)
        self._cloud_client.publish(topic, json.dumps(payload), qos=1)
        logger.info(f"[CloudMQTT] → {topic}  state={payload['state']}")

    def _publish_event(self, code: str, event: BayEvent, payload: dict):
        topic = CLOUD_TOPIC_EVENT.format(code=code)
        self._cloud_client.publish(topic, json.dumps(payload), qos=1)
        logger.info(f"[CloudMQTT] → {topic}  event={event.value}")

    # ── 心跳（每10秒）────────────────────────────────────────────────────────

    def _heartbeat_loop(self):
        while not self._stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
            payload = {"pi_id": PI_ID, "ts": datetime.now(timezone.utc).isoformat()}
            self._cloud_client.publish(CLOUD_TOPIC_HEARTBEAT, json.dumps(payload), qos=0)
            logger.debug("[CloudMQTT] ♥ heartbeat")

    # ── 图片接收 → LPR → 状态机 ──────────────────────────────────────────────

    def _on_image_received(self, code: str, image_path: str):
        if code not in self._bays:
            logger.warning(f"[LPR] 未知车位：{code}")
            return
        logger.info(f"[LPR] 开始识别：{image_path}")
        plate, confidence = self._lpr.recognise(image_path)
        self._bays[code].on_lpr_result(plate, confidence, image_path)