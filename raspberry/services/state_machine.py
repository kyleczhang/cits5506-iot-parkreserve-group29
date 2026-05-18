# =============================================================================
# services/state_machine.py  —  Per-bay reservation state machine
# =============================================================================
"""
State values (aligned with interface doc BayStateLiteral):
  available / reserved / occupied / pending_check_in /
  reserved_checked_in / conflict / offline

Event values (aligned with interface doc EventLiteral):
  sensor_online / sensor_offline /
  auto_check_in / pending_check_in / check_in_confirmed / conflict_strong
  (conflict_weak and no_show are handled by Backend scheduled tasks; Pi only reports state)

State transition diagram:
┌──────────────────────────────────────────────────────────────────────────┐
│  available ──[create]──► reserved                                        │
│                              │                                           │
│                     [sensor: vehicle arrives]                            │
│                              ▼                                           │
│                       pending_check_in ◄──[LPR failed/low confidence]   │
│                         │         │                                      │
│            [LPR match]  │         │ [LPR mismatch]                       │
│                         ▼         ▼                                      │
│             reserved_checked_in  conflict ◄──[manual check-in timeout]  │
│                                                                          │
│  pending_check_in ──[manual check-in]──► reserved_checked_in            │
│  conflict ──[Backend re-sends create]──► restore reservation cache       │
│                                          (wait for vehicle to leave → reserved) │
│  conflict ──[Backend re-sends check_in]──► reserved_checked_in          │
│                                            (check-in recovered)          │
│  reserved_checked_in ──[vehicle leaves]──► available                    │
│  conflict ──[vehicle leaves]──► available                                │
│                                 (Pi retains reservation cache,           │
│                                  awaits Backend decision)                │
│  reserved ──[arrival time + grace still empty]──► available              │
│                                                   (state report only)   │
│  available ──[vehicle present but no reservation]──► occupied            │
│  occupied ──[vehicle leaves]──► available                               │
└──────────────────────────────────────────────────────────────────────────┘

LED commands (plain strings, aligned with ESP32 interface doc):
  available           → ESP32 green light steady
  reserved            → ESP32 yellow light steady
  pending_check_in    → ESP32 yellow light blinking
  reserved_checked_in → ESP32 red light steady
  conflict_strong     → ESP32 red light blinking + buzzer
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


# ── State Enum ────────────────────────────────────────────────────────────────

class BayState(Enum):
    AVAILABLE           = "available"
    RESERVED            = "reserved"
    OCCUPIED            = "occupied"
    PENDING_CHECK_IN    = "pending_check_in"
    RESERVED_CHECKED_IN = "reserved_checked_in"
    CONFLICT            = "conflict"
    OFFLINE             = "offline"


# ── LED Command Strings (plain strings, parsed directly by ESP32) ─────────────

LED_COMMANDS = {
    BayState.AVAILABLE:            "available",
    BayState.RESERVED:             "reserved",
    BayState.PENDING_CHECK_IN:     "pending_check_in",
    BayState.RESERVED_CHECKED_IN:  "reserved_checked_in",
    BayState.OCCUPIED:             "reserved_checked_in",  # unbooked occupancy → solid red light
    BayState.CONFLICT:             "conflict_strong",
    BayState.OFFLINE:              None,
}


# ── Event Enum ────────────────────────────────────────────────────────────────

class BayEvent(Enum):
    SENSOR_ONLINE      = "sensor_online"
    SENSOR_OFFLINE     = "sensor_offline"
    AUTO_CHECK_IN      = "auto_check_in"
    PENDING_CHECK_IN   = "pending_check_in"
    CHECK_IN_CONFIRMED = "check_in_confirmed"
    CONFLICT_STRONG    = "conflict_strong"


# ── Reservation Data Structure ────────────────────────────────────────────────

@dataclass
class Reservation:
    reservation_id: str
    user_id: str
    bound_plates: List[str]
    expected_arrival_time: float  # Unix timestamp

    def __post_init__(self):
        self.bound_plates = [p.upper().replace(" ", "") for p in self.bound_plates]


# ── Per-Bay State Machine ─────────────────────────────────────────────────────

class BayStateMachine:
    """
    Manages the complete state machine for a single parking bay, thread-safe.

    Callbacks:
      on_led_command(code, cmd_str)        → send LED command to ESP32 (local MQTT)
      on_event(code, event, payload)       → report event to Backend (cloud MQTT)
      on_state_changed(code, payload)      → report state to Backend (cloud MQTT)
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

        logger.info(f"[{self.code}] State machine initialized → {self._state.value}")

    @property
    def state(self) -> BayState:
        return self._state

    @property
    def reservation(self) -> Optional[Reservation]:
        return self._reservation

    # ── Internal Utilities ────────────────────────────────────────────────────

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

    # ── State Transition (send LED + report state + report event) ─────────────

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

        # 1. Send LED command to ESP32
        cmd = LED_COMMANDS.get(new_state)
        if cmd is not None:
            self.on_led_command(self.code, cmd)

        # 2. Report state mirror to Backend
        state_payload = {
            "state":            new_state.value,
            "last_distance_cm": self._last_distance_cm,
            "ts":               self._now_iso(),
            "event_id":         self._new_event_id(),
        }
        self.on_state_changed(self.code, state_payload)

        # 3. Report event to Backend
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

    # ── Sensor Update (from ESP32 MQTT) ──────────────────────────────────────

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
            # vehicle leaves after successful check-in → release immediately
            self._reservation = None
            self._transition(BayState.AVAILABLE)

        elif self._state == BayState.CONFLICT:
            # vehicle leaves after strong conflict:
            # Pi retains reservation cache, reports available, awaits Backend decision
            # Backend will re-send create (restore reservation) or release (terminate)
            logger.info(f"[{self.code}] Vehicle left after conflict, reporting available, awaiting Backend decision")
            self._transition(BayState.AVAILABLE)
            # Note: do not clear self._reservation

        elif (self._reservation and
              time.time() < self._reservation.expected_arrival_time + self.no_show_grace):
            self._transition(BayState.RESERVED)

        else:
            self._reservation = None
            self._transition(BayState.AVAILABLE)

    # ── LPR Recognition Result ────────────────────────────────────────────────

    def on_lpr_result(self, plate: Optional[str], confidence: float, image_path: str):
        with self._lock:
            if self._state != BayState.PENDING_CHECK_IN:
                logger.warning(f"[{self.code}] LPR result arrived but state is {self._state.value}, ignoring")
                return
            if not self._reservation:
                logger.error(f"[{self.code}] No reservation record, cannot compare plate")
                return

            if plate is None or confidence < self.alpr_min_confidence:
                logger.info(f"[{self.code}] LPR confidence too low ({confidence:.2f}), waiting for manual check-in")
                return

            plate_norm = plate.upper().replace(" ", "")

            if plate_norm in self._reservation.bound_plates:
                logger.info(f"[{self.code}] LPR match: {plate_norm} ✓ → auto_check_in")
                self._cancel_timer()
                self._transition(
                    BayState.RESERVED_CHECKED_IN,
                    BayEvent.AUTO_CHECK_IN,
                    {"recognised_plate": plate_norm, "lpr_confidence": round(confidence, 4)},
                )
            else:
                logger.warning(f"[{self.code}] LPR mismatch: {plate_norm} ∉ {self._reservation.bound_plates}")
                self._cancel_timer()
                self._transition(
                    BayState.CONFLICT,
                    BayEvent.CONFLICT_STRONG,
                    {"recognised_plate": plate_norm, "lpr_confidence": round(confidence, 4)},
                )

    # ── Manual Check-in (Backend sends action=check_in) ──────────────────────

    def on_manual_checkin(self):
        with self._lock:
            if self._state == BayState.PENDING_CHECK_IN:
                self._cancel_timer()
                self._transition(BayState.RESERVED_CHECKED_IN, BayEvent.CHECK_IN_CONFIRMED)
            elif self._state == BayState.CONFLICT:
                # Recovery: strong conflict after check-in, Backend re-sends check_in to restore
                logger.info(f"[{self.code}] Received check_in recovery command during conflict → reserved_checked_in")
                self._transition(BayState.RESERVED_CHECKED_IN)
            else:
                logger.warning(f"[{self.code}] Received check_in, current state {self._state.value}, ignoring")

    # ── Manual Check-in Timeout (report state only, no event) ────────────────

    def _on_manual_checkin_timeout(self):
        with self._lock:
            if self._state == BayState.PENDING_CHECK_IN:
                logger.warning(f"[{self.code}] Manual check-in timeout → conflict (Backend handles conflict_weak internally)")
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

    # ── Reservation Created (Backend sends action=create) ─────────────────────

    def on_reservation_created(self, reservation: Reservation):
        with self._lock:
            if self._state not in (BayState.AVAILABLE, BayState.RESERVED, BayState.CONFLICT):
                logger.warning(f"[{self.code}] Bay not available for reservation, current: {self._state.value}")
                return

            self._reservation = reservation
            logger.info(f"[{self.code}] Reservation created/restored: {reservation.reservation_id}, "
                        f"plates: {reservation.bound_plates}")

            if self._state == BayState.CONFLICT:
                # Recovery: received create during conflict, only update reservation cache
                # wait for vehicle to leave and naturally return to reserved
                logger.info(f"[{self.code}] Restoring reservation cache during conflict, waiting for vehicle to leave to return to reserved")
            else:
                self._transition(BayState.RESERVED)
                delay = max(0.0, reservation.expected_arrival_time + self.no_show_grace - time.time())
                self._start_timer(delay, self._on_no_show_check)

    # ── Plate List Updated (Backend sends action=update_plates) ──────────────

    def on_plates_updated(self, bound_plates: List[str]):
        with self._lock:
            if self._reservation:
                self._reservation.bound_plates = [p.upper().replace(" ", "") for p in bound_plates]
                logger.info(f"[{self.code}] Bound plates updated: {self._reservation.bound_plates}")

    # ── Reservation Cancelled/Released (Backend sends action=cancel/release/expire_check_in) ──

    def on_reservation_cancelled(self):
        with self._lock:
            self._cancel_timer()
            self._reservation = None
            if self._vehicle_present:
                self._transition(BayState.OCCUPIED)
            else:
                self._transition(BayState.AVAILABLE)

    # ── No-show Detection (report state only, no event) ──────────────────────

    def _on_no_show_check(self):
        with self._lock:
            if self._state == BayState.RESERVED and not self._vehicle_present:
                logger.info(f"[{self.code}] No-show → releasing bay (Backend handles no_show event internally)")
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

    # ── Resync (Backend requests Pi to re-report current state) ──────────────

    def replay_state(self):
        with self._lock:
            self.on_state_changed(self.code, {
                "state":            self._state.value,
                "last_distance_cm": self._last_distance_cm,
                "ts":               self._now_iso(),
                "event_id":         self._new_event_id(),
            })
            logger.info(f"[{self.code}] resync → re-reporting state {self._state.value}")

    # ── State Snapshot (for debugging) ───────────────────────────────────────

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
