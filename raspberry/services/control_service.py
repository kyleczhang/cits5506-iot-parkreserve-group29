# =============================================================================
# services/control_service.py  —  树莓派控制逻辑主服务（对齐接口文档）
# =============================================================================
"""
MQTT 话题总览（完全对齐接口文档）
─────────────────────────────────────────────────────────────────────────────
本地（ESP32 ↔ Pi，Mosquitto）：
  bay/<code>/status   SUB  {"occupied": bool, "distance_cm": float}
  bay/<code>/led      PUB  {"color": str, "blink": bool, "buzzer": bool}

云端（Pi ↔ Backend，HiveMQ，TLS）：
  Pi → Backend：
    cloud/bay/<code>/state     PUB  StatePayload
    cloud/bay/<code>/event     PUB  EventPayload
    cloud/system/heartbeat     PUB  HeartbeatPayload（每10s）

  Backend → Pi：
    cloud/bay/<code>/reservation  SUB  ReservationCommand
    cloud/system/resync           SUB  空 payload，触发 Pi 重新上报所有状态
─────────────────────────────────────────────────────────────────────────────

ReservationCommand.action 值（接口文档）：
  create        → 预约创建
  cancel        → 预约取消
  check_in      → 用户手动 check-in（QR 或按钮）
  update_plates → 用户增删车牌，下发最新列表
"""

import json
import logging
import os
import ssl
import threading
import time
from datetime import datetime, timezone
from typing import Dict

import paho.mqtt.client as mqtt

try:
    from openalpr import Alpr
    ALPR_AVAILABLE = True
except ImportError:
    ALPR_AVAILABLE = False
    logging.warning("OpenALPR 未安装，将使用 Mock LPR（仅开发用途）")

from config.settings import (
    LOCAL_MQTT_HOST, LOCAL_MQTT_PORT, LOCAL_MQTT_CLIENT_ID,
    LOCAL_TOPIC_STATUS, LOCAL_TOPIC_LED,
    CLOUD_MQTT_HOST, CLOUD_MQTT_PORT, CLOUD_MQTT_USERNAME,
    CLOUD_MQTT_PASSWORD, CLOUD_MQTT_CLIENT_ID,
    CLOUD_TOPIC_STATE, CLOUD_TOPIC_EVENT, CLOUD_TOPIC_HEARTBEAT,
    CLOUD_TOPIC_RESERVATION, CLOUD_TOPIC_RESYNC,
    IMAGE_RECEIVER_HOST, IMAGE_RECEIVER_PORT, IMAGE_UPLOAD_DIR,
    ALPR_COUNTRY, ALPR_MIN_CONFIDENCE,
    NO_SHOW_GRACE_SECONDS, MANUAL_CHECKIN_GRACE_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS, PI_ID, BAY_CODES,
)
from services.state_machine import BayStateMachine, Reservation, BayEvent
from services.image_receiver import ImageReceiverService

logger = logging.getLogger(__name__)


# ── OpenALPR 封装 ─────────────────────────────────────────────────────────────

class LPRService:
    """
    封装 OpenALPR，统一返回 (plate | None, confidence: float 0-1)。
    接口文档要求 lpr_confidence 是 0-1 的小数。
    """

    def __init__(self, country: str = "au", min_confidence: float = 0.80):
        self.min_confidence = min_confidence
        # Mock 控制（调试用，部署后 ALPR_AVAILABLE=True 自动跳过）
        self.mock_plate      = "CZH5506"
        self.mock_confidence = 0.95      # 0-1 小数

        if ALPR_AVAILABLE:
            self._alpr = Alpr(
                country,
                "/etc/openalpr/openalpr.conf",
                "/usr/share/openalpr/runtime_data",
            )
            self._alpr.set_top_n(1)
            logger.info("OpenALPR 初始化完成")
        else:
            self._alpr = None

    def recognise(self, image_path: str):
        """返回 (plate: str | None, confidence: float 0-1)"""
        if not os.path.exists(image_path):
            logger.error(f"[LPR] 图片不存在：{image_path}")
            return None, 0.0

        if self._alpr is None:
            logger.warning(f"[LPR Mock] plate={self.mock_plate}, conf={self.mock_confidence}")
            return self.mock_plate, self.mock_confidence

        try:
            results = self._alpr.recognize_file(image_path)
            if results["results"]:
                best = results["results"][0]["candidates"][0]
                plate      = best["plate"]
                confidence = best["confidence"] / 100.0  # OpenALPR 返回 0-100，转成 0-1
                logger.info(f"[LPR] {plate}，置信度：{confidence:.2f}")
                return plate, confidence
            return None, 0.0
        except Exception as e:
            logger.error(f"[LPR] 识别异常：{e}")
            return None, 0.0

    def cleanup(self):
        if self._alpr:
            self._alpr.unload()


# ── 主控服务 ──────────────────────────────────────────────────────────────────

class ControlService:

    def __init__(self):
        self._lpr = LPRService(ALPR_COUNTRY, ALPR_MIN_CONFIDENCE)

        # 每个车位一个状态机
        self._bays: Dict[str, BayStateMachine] = {
            code: BayStateMachine(
                code=code,
                on_led_command=self._publish_led_command,
                on_event=self._publish_event,
                on_state_changed=self._publish_state,
                manual_checkin_grace=MANUAL_CHECKIN_GRACE_SECONDS,
                no_show_grace=NO_SHOW_GRACE_SECONDS,
                alpr_min_confidence=ALPR_MIN_CONFIDENCE,
            )
            for code in BAY_CODES
        }

        # 本地 MQTT（Mosquitto）
        self._local_client = mqtt.Client(
            client_id=LOCAL_MQTT_CLIENT_ID, protocol=mqtt.MQTTv5
        )
        self._local_client.on_connect = self._on_local_connect
        self._local_client.on_message = self._on_local_message

        # 云端 MQTT（HiveMQ，TLS）
        self._cloud_client = mqtt.Client(
            client_id=CLOUD_MQTT_CLIENT_ID, protocol=mqtt.MQTTv5
        )
        self._cloud_client.username_pw_set(CLOUD_MQTT_USERNAME, CLOUD_MQTT_PASSWORD)
        self._cloud_client.tls_set(
            cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS
        )
        self._cloud_client.on_connect    = self._on_cloud_connect
        self._cloud_client.on_message    = self._on_cloud_message
        self._cloud_client.on_disconnect = self._on_cloud_disconnect

        # HTTP 图片接收服务
        self._image_receiver = ImageReceiverService(
            upload_dir=IMAGE_UPLOAD_DIR,
            on_image_received=self._on_image_received,
            host=IMAGE_RECEIVER_HOST,
            port=IMAGE_RECEIVER_PORT,
        )

        self._stop_event = threading.Event()
    
    def _get_status(self) -> dict:
        return {
            "bays": {
                code: sm.get_snapshot()
                for code, sm in self._bays.items()
            }
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 启动 / 停止
    # ─────────────────────────────────────────────────────────────────────────

    def start(self):
        logger.info("=== ControlService 启动 ===")

        self._image_receiver.run()

        self._local_client.connect(LOCAL_MQTT_HOST, LOCAL_MQTT_PORT, keepalive=60)
        self._local_client.loop_start()

        self._cloud_client.connect(CLOUD_MQTT_HOST, CLOUD_MQTT_PORT, keepalive=60)
        self._cloud_client.loop_start()

        # 心跳线程
        threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="heartbeat"
        ).start()

        logger.info("=== ControlService 运行中 ===")

    def stop(self):
        self._stop_event.set()
        self._local_client.loop_stop()
        self._cloud_client.loop_stop()
        self._lpr.cleanup()
        logger.info("=== ControlService 已停止 ===")

    # ─────────────────────────────────────────────────────────────────────────
    # 本地 MQTT 回调（ESP32 ↔ Pi）
    # ─────────────────────────────────────────────────────────────────────────

    def _on_local_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("[LocalMQTT] 连接成功")
            client.subscribe(LOCAL_TOPIC_STATUS, qos=1)
        else:
            logger.error(f"[LocalMQTT] 连接失败 rc={rc}")

    def _on_local_message(self, client, userdata, msg):
        """
        接收 ESP32 传感器状态。
        话题：bay/<code>/status
        Payload：{"occupied": true, "distance_cm": 12.5}
        """
        parts = msg.topic.split("/")
        if len(parts) != 3:
            return

        code = parts[1]
        if code not in self._bays:
            logger.warning(f"[LocalMQTT] 未知车位：{code}")
            return

        try:
            data = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            logger.warning(f"[LocalMQTT] 无效 JSON：{msg.payload}")
            return

        occupied    = bool(data.get("occupied", False))
        distance_cm = float(data.get("distance_cm", 0.0))

        self._bays[code].on_sensor_update(occupied, distance_cm)

    # ─────────────────────────────────────────────────────────────────────────
    # 发布 LED 指令给 ESP32（本地 MQTT）
    # ─────────────────────────────────────────────────────────────────────────

    def _publish_led_command(self, code: str, command: dict):
        """
        Payload 示例：
          {"color": "red", "blink": true, "buzzer": true}
        """
        topic = LOCAL_TOPIC_LED.format(code=code)
        self._local_client.publish(topic, json.dumps(command), qos=1)
        logger.info(f"[LocalMQTT] → {topic}  {command}")

    # ─────────────────────────────────────────────────────────────────────────
    # 云端 MQTT 回调（Pi ↔ Backend）
    # ─────────────────────────────────────────────────────────────────────────

    def _on_cloud_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("[CloudMQTT] 连接成功")
            client.subscribe(CLOUD_TOPIC_RESERVATION, qos=1)
            client.subscribe(CLOUD_TOPIC_RESYNC, qos=1)
            logger.info("[CloudMQTT] 订阅：reservation + resync")

            # Pi 重启后主动请求 Backend 重新推送所有预约数据
            client.publish(
                "cloud/system/resync",
                json.dumps({"request": "replay"}),
                qos=1
            )
        else:
            logger.error(f"[CloudMQTT] 连接失败 rc={rc}")

    def _on_cloud_disconnect(self, client, userdata, rc, properties=None):
        logger.warning(f"[CloudMQTT] 断开（rc={rc}），等待自动重连…")

    def _on_cloud_message(self, client, userdata, msg):
        topic = msg.topic

        # ── cloud/system/resync ───────────────────────────────────────────
        if topic == CLOUD_TOPIC_RESYNC.replace("+", "").rstrip("/") or topic == "cloud/system/resync":
            logger.info("[CloudMQTT] 收到 resync 请求，重新上报所有状态")
            # for sm in self._bays.values():
            #     sm.replay_state()
            # return
            try:
                data = json.loads(msg.payload.decode())
                if data.get("request") != "replay":
                    logger.warning(f"[CloudMQTT] resync payload 格式错误：{data}")
                    return
            except json.JSONDecodeError:
                logger.warning(f"[CloudMQTT] resync payload 无效 JSON")
                return
            logger.info("[CloudMQTT] 收到 resync 请求，重新上报所有状态")
            for sm in self._bays.values():
                sm.replay_state()
            return

        # ── cloud/bay/<code>/reservation ─────────────────────────────────
        parts = topic.split("/")
        if len(parts) == 4 and parts[0] == "cloud" and parts[1] == "bay" and parts[3] == "reservation":
            code = parts[2]
            try:
                data = json.loads(msg.payload.decode())
            except json.JSONDecodeError:
                logger.warning(f"[CloudMQTT] 无效 JSON：{msg.payload}")
                return
            self._on_reservation_command(code, data)

    def _on_reservation_command(self, code: str, data: dict):
        """
        处理 ReservationCommand（接口文档）。
        action: create | cancel | check_in | update_plates
        """
        if code not in self._bays:
            logger.warning(f"[CloudMQTT] 未知车位：{code}")
            return

        action = data.get("action")
        sm = self._bays[code]

        if action == "create":
            # expected_arrival_time 是 ISO datetime 字符串
            try:
                arrival_iso = data["expected_arrival_time"]
                arrival_ts  = datetime.fromisoformat(arrival_iso).timestamp()
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
            # 用户通过 QR 或 App 按钮手动 check-in
            logger.info(f"[CloudMQTT] {code} 手动 check-in")
            sm.on_manual_checkin()

        elif action == "update_plates":
            # 用户增删车牌，Backend 推送最新列表
            plates = data.get("bound_plates", [])
            logger.info(f"[CloudMQTT] {code} 车牌列表更新：{plates}")
            sm.on_plates_updated(plates)

        elif action == "release":
            # Backend 通知 Pi 释放车位
            # reason: no_show / completed / abandoned / admin_override
            reason = data.get("reason", "unknown")
            logger.info(f"[CloudMQTT] {code} 收到 release，原因：{reason}")
            sm.on_reservation_cancelled()

        elif action == "expire_check_in":
            # Backend 通知 Pi check-in 窗口已过期
            logger.info(f"[CloudMQTT] {code} 收到 expire_check_in")
            sm.on_reservation_cancelled()

        else:
            logger.warning(f"[CloudMQTT] 未知 action：{action}")

    # ─────────────────────────────────────────────────────────────────────────
    # 发布状态镜像给云端（StatePayload）
    # ─────────────────────────────────────────────────────────────────────────

    def _publish_state(self, code: str, payload: dict):
        """
        由 BayStateMachine.on_state_changed 回调触发。
        格式（接口文档 StatePayload）：
          {state, last_distance_cm, ts, event_id}
        """
        topic = CLOUD_TOPIC_STATE.format(code=code)
        self._cloud_client.publish(topic, json.dumps(payload), qos=1)
        logger.debug(f"[CloudMQTT] → {topic}  state={payload['state']}")

    # ─────────────────────────────────────────────────────────────────────────
    # 发布事件给云端（EventPayload）
    # ─────────────────────────────────────────────────────────────────────────

    def _publish_event(self, code: str, event: BayEvent, payload: dict):
        """
        由 BayStateMachine.on_event 回调触发。
        格式（接口文档 EventPayload）：
          {event, ts, event_id, reservation_id, recognised_plate?, lpr_confidence?}
        """
        topic = CLOUD_TOPIC_EVENT.format(code=code)
        self._cloud_client.publish(topic, json.dumps(payload), qos=1)
        logger.info(f"[CloudMQTT] → {topic}  event={event.value}")

    # ─────────────────────────────────────────────────────────────────────────
    # 心跳（HeartbeatPayload，每10s）
    # ─────────────────────────────────────────────────────────────────────────

    def _heartbeat_loop(self):
        """
        接口文档：cloud/system/heartbeat，QoS 0，每~10s。
        Backend 超过30s未收到则将 Pi 管理的 bay 状态标为 offline。
        HeartbeatPayload：{pi_id, ts}
        """
        while not self._stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
            payload = {
                "pi_id": PI_ID,
                "ts":    datetime.now(timezone.utc).isoformat(),
            }
            self._cloud_client.publish(
                CLOUD_TOPIC_HEARTBEAT, json.dumps(payload), qos=0
            )
            logger.debug(f"[CloudMQTT] ♥ heartbeat")

    # ─────────────────────────────────────────────────────────────────────────
    # 图片接收回调 → LPR → 状态机
    # ─────────────────────────────────────────────────────────────────────────

    def _on_image_received(self, code: str, image_path: str):
        """
        ESP32 上传 JPEG 后由 ImageReceiverService 回调。
        在后台线程中执行，不阻塞 HTTP 响应。
        """
        if code not in self._bays:
            logger.warning(f"[LPR] 未知车位：{code}")
            return

        logger.info(f"[LPR] 开始识别：{image_path}")
        plate, confidence = self._lpr.recognise(image_path)
        self._bays[code].on_lpr_result(plate, confidence, image_path)
