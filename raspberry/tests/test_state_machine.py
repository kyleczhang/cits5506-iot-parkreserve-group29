# =============================================================================
# tests/test_state_machine.py  —  状态机单元测试（对齐接口文档）
# =============================================================================

import time
import pytest
from unittest.mock import MagicMock

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.state_machine import BayStateMachine, BayState, BayEvent, Reservation


def make_sm(manual_grace=300, no_show_grace=300):
    on_led          = MagicMock()
    on_event        = MagicMock()
    on_state_changed = MagicMock()
    sm = BayStateMachine(
        code="A1",
        on_led_command=on_led,
        on_event=on_event,
        on_state_changed=on_state_changed,
        manual_checkin_grace=manual_grace,
        no_show_grace=no_show_grace,
        alpr_min_confidence=0.80,
    )
    return sm, on_led, on_event, on_state_changed


def make_reservation(plates=None, arrival_offset=60):
    return Reservation(
        reservation_id="res-001",
        user_id="user-001",
        bound_plates=plates or ["1ABC234"],
        expected_arrival_time=time.time() + arrival_offset,
    )


# ── 基础状态转换 ───────────────────────────────────────────────────────────────

class TestBasicTransitions:

    def test_initial_state_is_available(self):
        sm, *_ = make_sm()
        assert sm.state == BayState.AVAILABLE

    def test_reservation_created_transitions_to_reserved(self):
        sm, on_led, _, __ = make_sm()
        sm.on_reservation_created(make_reservation())
        assert sm.state == BayState.RESERVED
        on_led.assert_called_with("A1", {"color": "yellow", "blink": False, "buzzer": False})

    def test_casual_vehicle_arrives(self):
        sm, on_led, _, __ = make_sm()
        sm.on_sensor_update(True, 12.0)
        # 无预约 → occupied
        assert sm.state == BayState.OCCUPIED
        on_led.assert_called_with("A1", {"color": "red", "blink": False, "buzzer": False})

    def test_casual_vehicle_leaves(self):
        sm, *_ = make_sm()
        sm.on_sensor_update(True, 12.0)
        sm.on_sensor_update(False, 300.0)
        assert sm.state == BayState.AVAILABLE

    def test_reserved_vehicle_arrives_goes_pending(self):
        sm, _, on_event, __ = make_sm()
        sm.on_reservation_created(make_reservation())
        sm.on_sensor_update(True, 12.0)
        assert sm.state == BayState.PENDING_CHECK_IN
        events = [c.args[1] for c in on_event.call_args_list]
        assert BayEvent.PENDING_CHECK_IN in events

    def test_state_changed_callback_called_on_transition(self):
        sm, _, __, on_state_changed = make_sm()
        sm.on_sensor_update(True, 12.0)
        # on_state_changed 应该被调用
        assert on_state_changed.called
        payload = on_state_changed.call_args[0][1]
        assert payload["state"] == "occupied"
        assert "last_distance_cm" in payload
        assert "ts" in payload
        assert "event_id" in payload


# ── LPR 结果处理 ───────────────────────────────────────────────────────────────

class TestLPRResults:

    def setup_method(self):
        self.sm, self.on_led, self.on_event, _ = make_sm()
        self.sm.on_reservation_created(make_reservation(plates=["1ABC234", "5XYZ789"]))
        self.sm.on_sensor_update(True, 12.0)
        assert self.sm.state == BayState.PENDING_CHECK_IN

    def test_lpr_match_plate1_auto_checkin(self):
        self.sm.on_lpr_result("1ABC234", 0.95, "/tmp/test.jpg")
        assert self.sm.state == BayState.RESERVED_CHECKED_IN
        events = [c.args[1] for c in self.on_event.call_args_list]
        assert BayEvent.AUTO_CHECK_IN in events

    def test_lpr_match_plate2_auto_checkin(self):
        self.sm.on_lpr_result("5XYZ789", 0.90, "/tmp/test.jpg")
        assert self.sm.state == BayState.RESERVED_CHECKED_IN

    def test_lpr_case_insensitive(self):
        self.sm.on_lpr_result("1abc234", 0.92, "/tmp/test.jpg")
        assert self.sm.state == BayState.RESERVED_CHECKED_IN

    def test_lpr_mismatch_conflict(self):
        self.sm.on_lpr_result("9ZZZ999", 0.95, "/tmp/test.jpg")
        assert self.sm.state == BayState.CONFLICT
        self.on_led.assert_called_with("A1", {"color": "red", "blink": True, "buzzer": True})
        events = [c.args[1] for c in self.on_event.call_args_list]
        assert BayEvent.CONFLICT_STRONG in events

    def test_lpr_mismatch_event_has_plate_and_confidence(self):
        """接口文档要求 conflict_strong 事件携带 recognised_plate 和 lpr_confidence。"""
        self.sm.on_lpr_result("9ZZZ999", 0.95, "/tmp/test.jpg")
        conflict_calls = [c for c in self.on_event.call_args_list
                          if c.args[1] == BayEvent.CONFLICT_STRONG]
        assert len(conflict_calls) == 1
        payload = conflict_calls[0].args[2]
        assert payload["recognised_plate"] == "9ZZZ999"
        assert 0 <= payload["lpr_confidence"] <= 1

    def test_lpr_auto_checkin_event_has_plate_and_confidence(self):
        """接口文档要求 auto_check_in 事件携带 recognised_plate 和 lpr_confidence。"""
        self.sm.on_lpr_result("1ABC234", 0.95, "/tmp/test.jpg")
        checkin_calls = [c for c in self.on_event.call_args_list
                         if c.args[1] == BayEvent.AUTO_CHECK_IN]
        assert len(checkin_calls) == 1
        payload = checkin_calls[0].args[2]
        assert payload["recognised_plate"] == "1ABC234"
        assert 0 <= payload["lpr_confidence"] <= 1

    def test_lpr_low_confidence_stays_pending(self):
        self.sm.on_lpr_result("1ABC234", 0.60, "/tmp/test.jpg")  # 低于 0.80
        assert self.sm.state == BayState.PENDING_CHECK_IN

    def test_lpr_none_stays_pending(self):
        self.sm.on_lpr_result(None, 0.0, "/tmp/test.jpg")
        assert self.sm.state == BayState.PENDING_CHECK_IN


# ── 人工 check-in ──────────────────────────────────────────────────────────────

class TestManualCheckin:

    def test_manual_checkin_from_pending(self):
        sm, _, on_event, __ = make_sm()
        sm.on_reservation_created(make_reservation())
        sm.on_sensor_update(True, 12.0)
        sm.on_manual_checkin()
        assert sm.state == BayState.RESERVED_CHECKED_IN
        events = [c.args[1] for c in on_event.call_args_list]
        assert BayEvent.CHECK_IN_CONFIRMED in events

    def test_manual_checkin_timeout_conflict_weak(self):
        sm, on_led, on_event, __ = make_sm(manual_grace=0)
        sm.on_reservation_created(make_reservation())
        sm.on_sensor_update(True, 12.0)
        time.sleep(0.2)
        assert sm.state == BayState.CONFLICT
        on_led.assert_called_with("A1", {"color": "red", "blink": True, "buzzer": True})
        events = [c.args[1] for c in on_event.call_args_list]
        assert BayEvent.CONFLICT_WEAK in events


# ── update_plates ──────────────────────────────────────────────────────────────

class TestUpdatePlates:

    def test_update_plates_changes_bound_list(self):
        sm, _, __, ___ = make_sm()
        sm.on_reservation_created(make_reservation(plates=["1ABC234"]))
        sm.on_plates_updated(["1ABC234", "9NEW999"])
        assert "9NEW999" in sm.reservation.bound_plates

    def test_updated_plate_matches_lpr(self):
        """车牌更新后，LPR 应能匹配新车牌。"""
        sm, _, on_event, __ = make_sm()
        sm.on_reservation_created(make_reservation(plates=["1ABC234"]))
        sm.on_plates_updated(["1ABC234", "9NEW999"])
        sm.on_sensor_update(True, 12.0)
        sm.on_lpr_result("9NEW999", 0.92, "/tmp/test.jpg")
        assert sm.state == BayState.RESERVED_CHECKED_IN


# ── No-show ────────────────────────────────────────────────────────────────────

class TestNoShow:

    def test_no_show_releases_bay(self):
        sm, _, on_event, __ = make_sm(no_show_grace=0)
        res = Reservation(
            reservation_id="res-002",
            user_id="user-002",
            bound_plates=["2DEF567"],
            expected_arrival_time=time.time() - 1,
        )
        sm.on_reservation_created(res)
        time.sleep(0.2)
        assert sm.state == BayState.AVAILABLE
        events = [c.args[1] for c in on_event.call_args_list]
        assert BayEvent.NO_SHOW in events


# ── resync ─────────────────────────────────────────────────────────────────────

class TestResync:

    def test_replay_state_calls_on_state_changed(self):
        sm, _, __, on_state_changed = make_sm()
        on_state_changed.reset_mock()
        sm.replay_state()
        assert on_state_changed.called
        payload = on_state_changed.call_args[0][1]
        assert payload["state"] == "available"
        assert "event_id" in payload


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
