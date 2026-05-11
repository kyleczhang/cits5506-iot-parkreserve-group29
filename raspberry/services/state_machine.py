# =============================================================================
# services/state_machine.py  —  每个车位的预约状态机（对齐接口文档）
# =============================================================================
"""
接口文档定义的状态值（BayStateLiteral）：
  available / reserved / occupied / pending_check_in /
  reserved_checked_in / conflict / offline

接口文档定义的事件值（EventLiteral）：
  sensor_online / sensor_offline /
  auto_check_in / pending_check_in / check_in_confirmed /
  conflict_strong / conflict_weak / no_show

状态转换图：
┌──────────────────────────────────────────────────────────────────────────┐
│  available  ──[create]──►  reserved                                      │
│                                │                                         │
│                       [sensor: vehicle arrives]                          │
│                                ▼                                         │
│                         pending_check_in  ◄──[LPR失败/低置信]              │
│                           │         │                                    │
│              [LPR匹配成功] │         │ [LPR不匹配]                         │
│                           ▼         ▼                                    │
│               reserved_checked_in  conflict  ◄──[人工check-in超时]        │
│                                                                          │
│  pending_check_in ──[人工check-in成功]──► reserved_checked_in            │
│  reserved ──[到达时间+grace仍空]──► available  (emit: no_show)           │
│  reserved/pending/checked_in/conflict ──[车辆离开]──► available          │
│  available ──[有车但无预约]──► occupied                                  │
│  occupied ──[车辆离开]──► available                                      │
└──────────────────────────────────────────────────────────────────────────┘

LED/蜂鸣器映射（发给 ESP32）：
  available           → green  solid  buzzer:off
  reserved            → yellow solid  buzzer:off
  pending_check_in    → yellow blink  buzzer:off
  reserved_checked_in → red    solid  buzzer:off
  occupied            → red    solid  buzzer:off
  conflict            → red    blink  buzzer:ON
  offline             → (不发指令，保持上一状态)
"""

import threading
import time
import uuid
import logging
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Callable

logger = logging.getLogger(__name__)


# ── 状态枚举（与接口文档 BayStateLiteral 完全一致）───────────────────────────

class BayState(Enum):
    AVAILABLE           = "available"
    RESERVED            = "reserved"
    OCCUPIED            = "occupied"            # casual，无预约
    PENDING_CHECK_IN    = "pending_check_in"
    RESERVED_CHECKED_IN = "reserved_checked_in"
    CONFLICT            = "conflict"            # 合并 strong + weak
    OFFLINE             = "offline"


# ── LED/蜂鸣器指令（发布到本地 MQTT bay/<code>/led）─────────────────────────

LED_COMMANDS = {
    BayState.AVAILABLE:            {"color": "green",  "blink": False, "buzzer": False},
    BayState.RESERVED:             {"color": "yellow", "blink": False, "buzzer": False},
    BayState.PENDING_CHECK_IN:     {"color": "yellow", "blink": True,  "buzzer": False},
    BayState.RESERVED_CHECKED_IN:  {"color": "red",    "blink": False, "buzzer": False},
    BayState.OCCUPIED:             {"color": "red",    "blink": False, "buzzer": False},
    BayState.CONFLICT:             {"color": "red",    "blink": True,  "buzzer": True},
    BayState.OFFLINE:              None,   # 不发 LED 指令
}


# ── 事件枚举（与接口文档 EventLiteral 完全一致）─────────────────────────────

class BayEvent(Enum):
    SENSOR_ONLINE       = "sensor_online"
    SENSOR_OFFLINE      = "sensor_offline"
    AUTO_CHECK_IN       = "auto_check_in"
    PENDING_CHECK_IN    = "pending_check_in"
    CHECK_IN_CONFIRMED  = "check_in_confirmed"
    CONFLICT_STRONG     = "conflict_strong"     # conflict 但有车牌证据
    CONFLICT_WEAK       = "conflict_weak"       # conflict 因人工check-in超时
    NO_SHOW             = "no_show"


# ── 预约数据结构（对应接口文档 ReservationCommand）──────────────────────────

@dataclass
class Reservation:
    reservation_id: str          # UUID string
    user_id: str                 # UUID string
    bound_plates: List[str]      # 该用户当前所有绑定车牌
    expected_arrival_time: float # Unix timestamp（从 ISO datetime 转换）

    def __post_init__(self):
        # 标准化：大写 + 去空格，便于 LPR 比对
        self.bound_plates = [p.upper().replace(" ", "") for p in self.bound_plates]


# ── 每个车位的状态机 ──────────────────────────────────────────────────────────

class BayStateMachine:
    """
    管理单个车位的完整状态机，线程安全。

    回调：
      on_led_command(code, cmd_dict)          → 触发本地 MQTT 发 LED 指令
      on_event(code, event, payload_dict)     → 触发云端 MQTT 上报事件
      on_state_changed(code, state, dist_cm)  → 触发云端 MQTT 上报状态镜像
    """

    def __init__(
        self,
        code: str,
        on_led_command: Callable,
        on_event: Callable,
        on_state_changed: Callable,
        manual_checkin_grace: int = 300,
        no_show_grace: int = 300,
        alpr_min_confidence: float = 0.80,
    ):
        self.code = code
        self.on_led_command   = on_led_command
        self.on_event         = on_event
        self.on_state_changed = on_state_changed
        self.manual_checkin_grace  = manual_checkin_grace
        self.no_show_grace         = no_show_grace
        self.alpr_min_confidence   = alpr_min_confidence

        self._lock           = threading.Lock()
        self._state          = BayState.AVAILABLE
        self._reservation: Optional[Reservation] = None
        self._vehicle_present = False
        self._last_distance_cm: float = 0.0   # 最近一次超声波读数，上报给云端
        self._timer: Optional[threading.Timer] = None

        logger.info(f"[{self.code}] 状态机初始化 → {self._state.value}")

    # ── 只读属性 ──────────────────────────────────────────────────────────────

    @property
    def state(self) -> BayState:
        return self._state

    @property
    def reservation(self) -> Optional[Reservation]:
        return self._reservation

    # ── 内部：生成事件 ID（UUID）─────────────────────────────────────────────

    @staticmethod
    def _new_event_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── 内部：状态转换 ─────────────────────────────────────────────────────────

    def _transition(
        self,
        new_state: BayState,
        event: Optional[BayEvent] = None,
        extra: dict = None,
    ):
        old_state = self._state
        self._state = new_state
        logger.info(f"[{self.code}] {old_state.value} → {new_state.value}"
                    + (f"  event={event.value}" if event else ""))

        # 1. 发 LED 指令给 ESP32
        cmd = LED_COMMANDS.get(new_state)
        if cmd is not None:
            self.on_led_command(self.code, cmd)

        # 2. 上报状态镜像给云端（StatePayload）
        #    格式：{state, last_distance_cm, ts, event_id}
        state_payload = {
            "state": new_state.value,
            "last_distance_cm": self._last_distance_cm,
            "ts": self._now_iso(),
            "event_id": self._new_event_id(),
        }
        self.on_state_changed(self.code, state_payload)

        # 3. 上报事件给云端（EventPayload）
        if event:
            event_payload = {
                "event":          event.value,
                "ts":             self._now_iso(),
                "event_id":       self._new_event_id(),
                "reservation_id": self._reservation.reservation_id if self._reservation else None,
            }
            if extra:
                event_payload.update(extra)
            self.on_event(self.code, event, event_payload)

    def _cancel_timer(self):
        if self._timer and self._timer.is_alive():
            self._timer.cancel()
        self._timer = None

    def _start_timer(self, seconds: float, callback, *args):
        self._cancel_timer()
        self._timer = threading.Timer(seconds, callback, args=args)
        self._timer.daemon = True
        self._timer.start()

    # ── 外部触发：传感器状态（来自 ESP32 本地 MQTT）──────────────────────────

    def on_sensor_update(self, occupied: bool, distance_cm: float = 0.0):
        """
        ESP32 每2秒发布一次传感器状态。
        payload 格式：{"occupied": true, "distance_cm": 12.5}
        """
        with self._lock:
            self._last_distance_cm = distance_cm
            prev = self._vehicle_present
            self._vehicle_present = occupied

            if occupied and not prev:
                self._handle_vehicle_arrived()
            elif not occupied and prev:
                self._handle_vehicle_left()

    def _handle_vehicle_arrived(self):
        if self._state == BayState.RESERVED:
            # 有预约 → pending，等待 LPR 结果
            self._transition(BayState.PENDING_CHECK_IN, BayEvent.PENDING_CHECK_IN)
            # 启动人工 check-in 超时计时器（LPR 失败的兜底）
            self._start_timer(self.manual_checkin_grace, self._on_manual_checkin_timeout)

        elif self._state == BayState.AVAILABLE:
            # 无预约 → casual 占用
            self._transition(BayState.OCCUPIED)

    def _handle_vehicle_left(self):
        self._cancel_timer()
        states_that_release = {
            BayState.RESERVED_CHECKED_IN,
            BayState.OCCUPIED,
            BayState.CONFLICT,
            BayState.PENDING_CHECK_IN,
        }
        if self._state in states_that_release:
            # 如果仍有有效预约且在时间窗口内，回到 reserved
            if (self._reservation and
                    time.time() < self._reservation.expected_arrival_time + self.no_show_grace):
                self._transition(BayState.RESERVED)
            else:
                self._reservation = None
                self._transition(BayState.AVAILABLE)

    # ── 外部触发：LPR 识别结果 ────────────────────────────────────────────────

    def on_lpr_result(self, plate: Optional[str], confidence: float, image_path: str):
        """
        confidence 范围 0-1（对应接口文档 lpr_confidence: 0~1）。
        plate=None 或 confidence < alpr_min_confidence → 识别失败，等待人工。
        """
        with self._lock:
            if self._state != BayState.PENDING_CHECK_IN:
                logger.warning(f"[{self.code}] LPR 结果到达但状态为 {self._state.value}，忽略")
                return
            if not self._reservation:
                logger.error(f"[{self.code}] 无预约记录，无法比对车牌")
                return

            # ── 置信度不足 / 识别失败 ────────────────────────────────────────
            if plate is None or confidence < self.alpr_min_confidence:
                logger.info(f"[{self.code}] LPR 置信度不足（{confidence:.2f}），等待人工 check-in")
                # 状态不变，计时器已在 _handle_vehicle_arrived 中启动
                return

            plate_norm = plate.upper().replace(" ", "")

            # ── 匹配成功 → auto_check_in ──────────────────────────────────────
            if plate_norm in self._reservation.bound_plates:
                logger.info(f"[{self.code}] LPR 匹配：{plate_norm} ✓ → auto_check_in")
                self._cancel_timer()
                self._transition(
                    BayState.RESERVED_CHECKED_IN,
                    BayEvent.AUTO_CHECK_IN,
                    {
                        "recognised_plate": plate_norm,
                        "lpr_confidence":   round(confidence, 4),  # 0-1 小数
                    }
                )

            # ── 不匹配 → conflict_strong ──────────────────────────────────────
            else:
                logger.warning(f"[{self.code}] LPR 不匹配：{plate_norm} ∉ {self._reservation.bound_plates}")
                self._cancel_timer()
                self._transition(
                    BayState.CONFLICT,
                    BayEvent.CONFLICT_STRONG,
                    {
                        "recognised_plate": plate_norm,
                        "lpr_confidence":   round(confidence, 4),
                    }
                )

    # ── 外部触发：人工 check-in（云端下发 action=check_in）──────────────────

    def on_manual_checkin(self):
        with self._lock:
            if self._state == BayState.PENDING_CHECK_IN:
                self._cancel_timer()
                self._transition(BayState.RESERVED_CHECKED_IN, BayEvent.CHECK_IN_CONFIRMED)
            else:
                logger.warning(f"[{self.code}] 收到人工 check-in，状态为 {self._state.value}，忽略")

    # ── 内部定时器：人工 check-in 超时 → conflict（weak）────────────────────

    # def _on_manual_checkin_timeout(self):
    #     with self._lock:
    #         if self._state == BayState.PENDING_CHECK_IN:
    #             logger.warning(f"[{self.code}] 人工 check-in 超时 → conflict_weak")
    #             self._transition(BayState.CONFLICT, BayEvent.CONFLICT_WEAK)

    def _on_manual_checkin_timeout(self):
        with self._lock:
            if self._state == BayState.PENDING_CHECK_IN:
                logger.warning(f"[{self.code}] 人工 check-in 超时 → conflict")
                # 只转换状态，不发事件给 Backend（Backend 自己内部处理）
                self._state = BayState.CONFLICT
                cmd = LED_COMMANDS.get(BayState.CONFLICT)
                if cmd:
                    self.on_led_command(self.code, cmd)
                state_payload = {
                    "state":            BayState.CONFLICT.value,
                    "last_distance_cm": self._last_distance_cm,
                    "ts":               self._now_iso(),
                    "event_id":         self._new_event_id(),
                }
                self.on_state_changed(self.code, state_payload)

    # ── 外部触发：预约创建（云端下发 action=create）──────────────────────────

    def on_reservation_created(self, reservation: Reservation):
        with self._lock:
            if self._state not in (BayState.AVAILABLE, BayState.RESERVED):
                logger.warning(f"[{self.code}] 车位不可预约，当前：{self._state.value}")
                return
            self._reservation = reservation
            logger.info(f"[{self.code}] 预约创建：{reservation.reservation_id}，"
                        f"车牌列表：{reservation.bound_plates}")
            self._transition(BayState.RESERVED)

            # no_show 计时器
            delay = max(0.0, reservation.expected_arrival_time + self.no_show_grace - time.time())
            self._start_timer(delay, self._on_no_show_check)

    # ── 外部触发：车牌列表更新（云端下发 action=update_plates）──────────────

    def on_plates_updated(self, bound_plates: List[str]):
        """用户在 App 上增删车牌，Backend 立即推送最新列表。"""
        with self._lock:
            if self._reservation:
                self._reservation.bound_plates = [
                    p.upper().replace(" ", "") for p in bound_plates
                ]
                logger.info(f"[{self.code}] 绑定车牌更新：{self._reservation.bound_plates}")

    # ── 外部触发：预约取消（云端下发 action=cancel）──────────────────────────

    def on_reservation_cancelled(self):
        with self._lock:
            self._cancel_timer()
            self._reservation = None
            if self._vehicle_present:
                self._transition(BayState.OCCUPIED)
            else:
                self._transition(BayState.AVAILABLE)

    # ── 内部定时器：no_show 检测 ──────────────────────────────────────────────

    def _on_no_show_check(self):
        # with self._lock:
        #     if self._state == BayState.RESERVED and not self._vehicle_present:
        #         logger.info(f"[{self.code}] No-show → 释放车位")
        #         self._reservation = None
        #         self._transition(BayState.AVAILABLE, BayEvent.NO_SHOW)
        with self._lock:
            if self._state == BayState.RESERVED and not self._vehicle_present:
                logger.info(f"[{self.code}] No-show → 释放车位（只上报state，不发event）")
                self._reservation = None
                self._state = BayState.AVAILABLE
                cmd = LED_COMMANDS.get(BayState.AVAILABLE)
                if cmd:
                    self.on_led_command(self.code, cmd)
                state_payload = {
                    "state":            BayState.AVAILABLE.value,
                    "last_distance_cm": self._last_distance_cm,
                    "ts":               self._now_iso(),
                    "event_id":         self._new_event_id(),
                }
                self.on_state_changed(self.code, state_payload)

    # ── 重同步：云端请求 Pi replay 当前状态 ──────────────────────────────────
    def replay_state(self):
        """收到 cloud/system/resync 后调用，重新上报当前状态快照。"""
        with self._lock:
            state_payload = {
                "state":            self._state.value,
                "last_distance_cm": self._last_distance_cm,
                "ts":               self._now_iso(),
                "event_id":         self._new_event_id(),
            }
            self.on_state_changed(self.code, state_payload)
            logger.info(f"[{self.code}] resync → 重新上报状态 {self._state.value}")

    # ── 状态快照（调试用）────────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        with self._lock:
            return {
                "code":             self.code,
                "state":            self._state.value,
                "vehicle_present":  self._vehicle_present,
                "distance_cm":      self._last_distance_cm,
                "reservation_id":   self._reservation.reservation_id if self._reservation else None,
            }
