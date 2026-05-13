# =============================================================================
# services/state_machine.py  —  每个车位的预约状态机
# =============================================================================
"""
状态值（对齐接口文档 BayStateLiteral）：
  available / reserved / occupied / pending_check_in /
  reserved_checked_in / conflict / offline

事件值（对齐接口文档 EventLiteral）：
  sensor_online / sensor_offline /
  auto_check_in / pending_check_in / check_in_confirmed / conflict_strong
  （conflict_weak 和 no_show 由 Backend 内部定时任务处理，Pi 只上报 state）

状态转换图：
┌──────────────────────────────────────────────────────────────────────────┐
│  available ──[create]──► reserved                                        │
│                              │                                           │
│                     [sensor: vehicle arrives]                            │
│                              ▼                                           │
│                       pending_check_in ◄──[LPR失败/低置信]               │
│                         │         │                                      │
│            [LPR匹配成功] │         │ [LPR不匹配]                          │
│                         ▼         ▼                                      │
│             reserved_checked_in  conflict ◄──[人工check-in超时]           │
│                                                                          │
│  pending_check_in ──[人工check-in]──► reserved_checked_in               │
│  conflict ──[Backend重发create]──► 恢复预约缓存（等车辆离开回reserved）    │
│  conflict ──[Backend重发check_in]──► reserved_checked_in（已签到恢复）    │
│  reserved_checked_in ──[车辆离开]──► available                           │
│  conflict ──[车辆离开]──► available（Pi保留预约缓存，等Backend决策）       │
│  reserved ──[到达时间+grace仍空]──► available（只上报state）              │
│  available ──[有车但无预约]──► occupied                                  │
│  occupied ──[车辆离开]──► available                                      │
└──────────────────────────────────────────────────────────────────────────┘

LED 指令（纯字符串，对齐 ESP32 接口文档）：
  available           → ESP32 绿灯常亮
  reserved            → ESP32 黄灯常亮
  pending_check_in    → ESP32 黄灯闪烁
  reserved_checked_in → ESP32 红灯常亮
  conflict_strong     → ESP32 红灯闪烁 + 蜂鸣器
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


# ── 状态枚举 ──────────────────────────────────────────────────────────────────

class BayState(Enum):
    AVAILABLE           = "available"
    RESERVED            = "reserved"
    OCCUPIED            = "occupied"
    PENDING_CHECK_IN    = "pending_check_in"
    RESERVED_CHECKED_IN = "reserved_checked_in"
    CONFLICT            = "conflict"
    OFFLINE             = "offline"


# ── LED 指令字符串（纯字符串，ESP32 直接解析）─────────────────────────────────

LED_COMMANDS = {
    BayState.AVAILABLE:            "available",
    BayState.RESERVED:             "reserved",
    BayState.PENDING_CHECK_IN:     "pending_check_in",
    BayState.RESERVED_CHECKED_IN:  "reserved_checked_in",
    BayState.OCCUPIED:             "reserved_checked_in",  # 无预约占用 → 红灯常亮
    BayState.CONFLICT:             "conflict_strong",
    BayState.OFFLINE:              None,
}


# ── 事件枚举 ──────────────────────────────────────────────────────────────────

class BayEvent(Enum):
    SENSOR_ONLINE      = "sensor_online"
    SENSOR_OFFLINE     = "sensor_offline"
    AUTO_CHECK_IN      = "auto_check_in"
    PENDING_CHECK_IN   = "pending_check_in"
    CHECK_IN_CONFIRMED = "check_in_confirmed"
    CONFLICT_STRONG    = "conflict_strong"


# ── 预约数据结构 ──────────────────────────────────────────────────────────────

@dataclass
class Reservation:
    reservation_id: str
    user_id: str
    bound_plates: List[str]
    expected_arrival_time: float  # Unix timestamp

    def __post_init__(self):
        self.bound_plates = [p.upper().replace(" ", "") for p in self.bound_plates]


# ── 每个车位的状态机 ──────────────────────────────────────────────────────────

class BayStateMachine:
    """
    管理单个车位的完整状态机，线程安全。

    回调：
      on_led_command(code, cmd_str)        → 发 LED 指令给 ESP32（本地 MQTT）
      on_event(code, event, payload)       → 上报事件给 Backend（云端 MQTT）
      on_state_changed(code, payload)      → 上报状态给 Backend（云端 MQTT）
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
        self.on_led_command        = on_led_command
        self.on_event              = on_event
        self.on_state_changed      = on_state_changed
        self.manual_checkin_grace  = manual_checkin_grace
        self.no_show_grace         = no_show_grace
        self.alpr_min_confidence   = alpr_min_confidence

        self._lock              = threading.Lock()
        self._state             = BayState.AVAILABLE
        self._reservation: Optional[Reservation] = None
        self._vehicle_present   = False
        self._last_distance_cm  = 0.0
        self._timer: Optional[threading.Timer] = None

        logger.info(f"[{self.code}] 状态机初始化 → {self._state.value}")

    @property
    def state(self) -> BayState:
        return self._state

    @property
    def reservation(self) -> Optional[Reservation]:
        return self._reservation

    # ── 内部工具 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _new_event_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _cancel_timer(self):
        if self._timer and self._timer.is_alive():
            self._timer.cancel()
        self._timer = None

    def _start_timer(self, seconds: float, callback, *args):
        self._cancel_timer()
        self._timer = threading.Timer(seconds, callback, args=args)
        self._timer.daemon = True
        self._timer.start()

    # ── 状态转换（发 LED + 上报 state + 上报 event）──────────────────────────

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

        # 2. 上报状态镜像给 Backend
        state_payload = {
            "state":            new_state.value,
            "last_distance_cm": self._last_distance_cm,
            "ts":               self._now_iso(),
            "event_id":         self._new_event_id(),
        }
        self.on_state_changed(self.code, state_payload)

        # 3. 上报事件给 Backend
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

    # ── 传感器更新（来自 ESP32 MQTT）─────────────────────────────────────────

    def on_sensor_update(self, occupied: bool, distance_cm: float = 0.0):
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
            self._transition(BayState.PENDING_CHECK_IN, BayEvent.PENDING_CHECK_IN)
            self._start_timer(self.manual_checkin_grace, self._on_manual_checkin_timeout)
        elif self._state == BayState.AVAILABLE:
            self._transition(BayState.OCCUPIED)

    def _handle_vehicle_left(self):
        self._cancel_timer()
        states_that_release = {
            BayState.RESERVED_CHECKED_IN,
            BayState.OCCUPIED,
            BayState.CONFLICT,
            BayState.PENDING_CHECK_IN,
        }
        if self._state not in states_that_release:
            return

        if self._state == BayState.RESERVED_CHECKED_IN:
            # check-in 成功后车辆离开 → 直接释放
            self._reservation = None
            self._transition(BayState.AVAILABLE)

        elif self._state == BayState.CONFLICT:
            # strong conflict 后车辆离开：
            # Pi 保留预约缓存，上报 available，等 Backend 决策
            # Backend 会重发 create（恢复预约）或 release（终止）
            logger.info(f"[{self.code}] conflict 后车辆离开，上报 available，等待 Backend 决策")
            self._transition(BayState.AVAILABLE)
            # 注意：不清除 self._reservation

        elif (self._reservation and
              time.time() < self._reservation.expected_arrival_time + self.no_show_grace):
            self._transition(BayState.RESERVED)

        else:
            self._reservation = None
            self._transition(BayState.AVAILABLE)

    # ── LPR 识别结果 ──────────────────────────────────────────────────────────

    def on_lpr_result(self, plate: Optional[str], confidence: float, image_path: str):
        with self._lock:
            if self._state != BayState.PENDING_CHECK_IN:
                logger.warning(f"[{self.code}] LPR 结果到达但状态为 {self._state.value}，忽略")
                return
            if not self._reservation:
                logger.error(f"[{self.code}] 无预约记录，无法比对车牌")
                return

            if plate is None or confidence < self.alpr_min_confidence:
                logger.info(f"[{self.code}] LPR 置信度不足（{confidence:.2f}），等待人工 check-in")
                return

            plate_norm = plate.upper().replace(" ", "")

            if plate_norm in self._reservation.bound_plates:
                logger.info(f"[{self.code}] LPR 匹配：{plate_norm} ✓ → auto_check_in")
                self._cancel_timer()
                self._transition(
                    BayState.RESERVED_CHECKED_IN,
                    BayEvent.AUTO_CHECK_IN,
                    {"recognised_plate": plate_norm, "lpr_confidence": round(confidence, 4)},
                )
            else:
                logger.warning(f"[{self.code}] LPR 不匹配：{plate_norm} ∉ {self._reservation.bound_plates}")
                self._cancel_timer()
                self._transition(
                    BayState.CONFLICT,
                    BayEvent.CONFLICT_STRONG,
                    {"recognised_plate": plate_norm, "lpr_confidence": round(confidence, 4)},
                )

    # ── 人工 check-in（Backend 下发 action=check_in）─────────────────────────

    def on_manual_checkin(self):
        with self._lock:
            if self._state == BayState.PENDING_CHECK_IN:
                self._cancel_timer()
                self._transition(BayState.RESERVED_CHECKED_IN, BayEvent.CHECK_IN_CONFIRMED)
            elif self._state == BayState.CONFLICT:
                # 恢复场景：已签到时发生 strong conflict，Backend 重发 check_in 恢复语义
                logger.info(f"[{self.code}] conflict 中收到 check_in 恢复指令 → reserved_checked_in")
                self._transition(BayState.RESERVED_CHECKED_IN)
            else:
                logger.warning(f"[{self.code}] 收到 check_in，当前状态 {self._state.value}，忽略")

    # ── 人工 check-in 超时（只上报 state，不发 event）────────────────────────

    def _on_manual_checkin_timeout(self):
        with self._lock:
            if self._state == BayState.PENDING_CHECK_IN:
                logger.warning(f"[{self.code}] 人工 check-in 超时 → conflict（Backend 自行处理 conflict_weak）")
                self._state = BayState.CONFLICT
                cmd = LED_COMMANDS.get(BayState.CONFLICT)
                if cmd:
                    self.on_led_command(self.code, cmd)
                self.on_state_changed(self.code, {
                    "state":            BayState.CONFLICT.value,
                    "last_distance_cm": self._last_distance_cm,
                    "ts":               self._now_iso(),
                    "event_id":         self._new_event_id(),
                })

    # ── 预约创建（Backend 下发 action=create）────────────────────────────────

    def on_reservation_created(self, reservation: Reservation):
        with self._lock:
            if self._state not in (BayState.AVAILABLE, BayState.RESERVED, BayState.CONFLICT):
                logger.warning(f"[{self.code}] 车位不可预约，当前：{self._state.value}")
                return

            self._reservation = reservation
            logger.info(f"[{self.code}] 预约创建/恢复：{reservation.reservation_id}，"
                        f"车牌列表：{reservation.bound_plates}")

            if self._state == BayState.CONFLICT:
                # 恢复场景：conflict 中收到 create，只更新预约缓存
                # 等车辆离开后自然回到 reserved
                logger.info(f"[{self.code}] conflict 中恢复预约缓存，等待车辆离开后回到 reserved")
            else:
                self._transition(BayState.RESERVED)
                delay = max(0.0, reservation.expected_arrival_time + self.no_show_grace - time.time())
                self._start_timer(delay, self._on_no_show_check)

    # ── 车牌列表更新（Backend 下发 action=update_plates）─────────────────────

    def on_plates_updated(self, bound_plates: List[str]):
        with self._lock:
            if self._reservation:
                self._reservation.bound_plates = [p.upper().replace(" ", "") for p in bound_plates]
                logger.info(f"[{self.code}] 绑定车牌更新：{self._reservation.bound_plates}")

    # ── 预约取消/释放（Backend 下发 action=cancel/release/expire_check_in）────

    def on_reservation_cancelled(self):
        with self._lock:
            self._cancel_timer()
            self._reservation = None
            if self._vehicle_present:
                self._transition(BayState.OCCUPIED)
            else:
                self._transition(BayState.AVAILABLE)

    # ── No-show 检测（只上报 state，不发 event）──────────────────────────────

    def _on_no_show_check(self):
        with self._lock:
            if self._state == BayState.RESERVED and not self._vehicle_present:
                logger.info(f"[{self.code}] No-show → 释放车位（Backend 自行处理 no_show 事件）")
                self._reservation = None
                self._state = BayState.AVAILABLE
                cmd = LED_COMMANDS.get(BayState.AVAILABLE)
                if cmd:
                    self.on_led_command(self.code, cmd)
                self.on_state_changed(self.code, {
                    "state":            BayState.AVAILABLE.value,
                    "last_distance_cm": self._last_distance_cm,
                    "ts":               self._now_iso(),
                    "event_id":         self._new_event_id(),
                })

    # ── Resync（Backend 请求 Pi 重新上报当前状态）────────────────────────────

    def replay_state(self):
        with self._lock:
            self.on_state_changed(self.code, {
                "state":            self._state.value,
                "last_distance_cm": self._last_distance_cm,
                "ts":               self._now_iso(),
                "event_id":         self._new_event_id(),
            })
            logger.info(f"[{self.code}] resync → 重新上报状态 {self._state.value}")

    # ── 状态快照（调试用）────────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        with self._lock:
            return {
                "code":           self.code,
                "state":          self._state.value,
                "vehicle_present": self._vehicle_present,
                "distance_cm":    self._last_distance_cm,
                "reservation_id": self._reservation.reservation_id if self._reservation else None,
                "bound_plates":   self._reservation.bound_plates if self._reservation else [],
            }