"""Reservation API tests spanning booking, cancellation, and manual check-in."""

from __future__ import annotations

import time
from datetime import timedelta

from app.extensions import db
from app.models import (
    BayState,
    Conflict,
    ConflictKind,
    ConflictResolution,
    ParkingBay,
    Payment,
    PaymentAction,
    PenaltyKind,
    Reservation,
    ReservationStatus,
)
from app.utils.time import utcnow
from tests.conftest import card_body


def _arrival_in(minutes: int) -> str:
    return (utcnow() + timedelta(minutes=minutes)).isoformat()


def _book(client, headers, card, *, bay_code: str, in_minutes: int):
    return client.post(
        "/api/v1/reservations",
        json={
            "bay_code": bay_code,
            "expected_arrival_time": _arrival_in(in_minutes),
            "card": card_body(card),
        },
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_reserve_emits_command_with_bound_plates(
    client,
    auth_headers,
    user_with_plates,
    bays,
    card,
    app,
):
    resp = _book(client, auth_headers, card, bay_code="A1", in_minutes=15)
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["bay_code"] == "A1"
    assert body["status"] == "active"
    assert body["payment"]["deposit_cents"] == 1000

    with app.app_context():
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.RESERVED
        assert bay.current_reservation_id is not None

        # Pre-auth payment row inserted in the same transaction (R20)
        pre_auth = db.session.execute(
            db.select(Payment).where(Payment.action == PaymentAction.PRE_AUTH)
        ).scalar_one()
        assert pre_auth.amount_cents == 1000
        assert pre_auth.reservation_id == bay.current_reservation_id


def test_reserve_rejected_when_user_has_no_plates(client, app, user, bays, card):
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity=str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    resp = _book(client, headers, card, bay_code="A1", in_minutes=10)
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "no_bound_plates"


def test_reserve_rejected_beyond_one_hour_window(client, auth_headers, bays, card):
    resp = _book(client, auth_headers, card, bay_code="A1", in_minutes=120)
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "outside_booking_window"


def test_reserve_rejected_when_arrival_in_past(client, auth_headers, bays, card):
    resp = _book(client, auth_headers, card, bay_code="A1", in_minutes=-5)
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "invalid_arrival_time"


def test_double_reserve_rejected_409(client, auth_headers, user_with_plates, bays, card):
    first = _book(client, auth_headers, card, bay_code="A1", in_minutes=10)
    assert first.status_code == 201
    second = _book(client, auth_headers, card, bay_code="A1", in_minutes=20)
    assert second.status_code == 409


def test_reserve_with_unknown_card_402(client, auth_headers, bays, user_with_plates):
    bad = type("C", (), {})()
    bad.number = "9999999999999999"
    bad.cvv = "000"
    bad.expiry_month = 12
    bad.expiry_year = 2030
    bad.holder_name = "Nobody"
    resp = client.post(
        "/api/v1/reservations",
        json={
            "bay_code": "A1",
            "expected_arrival_time": _arrival_in(20),
            "card": card_body(bad),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 402
    assert resp.get_json()["error"]["code"] == "card_invalid"


def test_reserve_with_expired_card_402(client, auth_headers, bays, user_with_plates, mock_cards):
    expired = mock_cards[2]  # seeded as expiry 2024
    bad = type("C", (), {})()
    bad.number = expired.card_number
    bad.cvv = expired.cvv
    bad.expiry_month = expired.expiry_month
    bad.expiry_year = expired.expiry_year
    bad.holder_name = expired.holder_name
    resp = client.post(
        "/api/v1/reservations",
        json={
            "bay_code": "A1",
            "expected_arrival_time": _arrival_in(20),
            "card": card_body(bad),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 402
    assert resp.get_json()["error"]["code"] == "card_expired"


def test_reserve_with_insufficient_funds_402(
    client,
    auth_headers,
    bays,
    user_with_plates,
    mock_cards,
):
    empty = mock_cards[1]
    bad = type("C", (), {})()
    bad.number = empty.card_number
    bad.cvv = empty.cvv
    bad.expiry_month = empty.expiry_month
    bad.expiry_year = empty.expiry_year
    bad.holder_name = empty.holder_name
    resp = client.post(
        "/api/v1/reservations",
        json={
            "bay_code": "A1",
            "expected_arrival_time": _arrival_in(20),
            "card": card_body(bad),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 402
    assert resp.get_json()["error"]["code"] == "insufficient_funds"


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


def test_cancel_far_in_advance_releases_full_deposit(
    client,
    auth_headers,
    bays,
    app,
    user_with_plates,
    card,
    monkeypatch,
):
    from app.services import reservation_service

    released: list[tuple[int, str]] = []
    monkeypatch.setattr(
        reservation_service,
        "push_deposit_released",
        lambda *, amount_cents, reason, **_: released.append((amount_cents, reason)),
    )

    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=45).get_json()
    resp = client.post(
        f"/api/v1/reservations/{created['id']}/cancel",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "cancelled"
    with app.app_context():
        rows = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(r.action.value for r in rows)
        assert actions == ["pre_auth", "release"]
        release = next(r for r in rows if r.action == PaymentAction.RELEASE)
        assert release.amount_cents == 1000  # full deposit returned
        # No penalty
        assert all(r.penalty_kind is None for r in rows)
    assert released == [(1000, "clean_cancel")]


def test_late_cancel_captures_penalty_and_releases_remainder(
    client,
    auth_headers,
    bays,
    app,
    user_with_plates,
    card,
    monkeypatch,
):
    from app.services import reservation_service

    released: list[tuple[int, str]] = []
    monkeypatch.setattr(
        reservation_service,
        "push_deposit_released",
        lambda *, amount_cents, reason, **_: released.append((amount_cents, reason)),
    )

    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=5).get_json()
    resp = client.post(
        f"/api/v1/reservations/{created['id']}/cancel",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "cancelled_late"
    with app.app_context():
        rows = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(r.action.value for r in rows)
        assert actions == ["penalty_capture", "pre_auth", "release"]
        penalty = next(r for r in rows if r.action == PaymentAction.PENALTY_CAPTURE)
        release = next(r for r in rows if r.action == PaymentAction.RELEASE)
        assert penalty.penalty_kind == PenaltyKind.LATE_CANCEL
        assert penalty.amount_cents == 500
        assert release.amount_cents == 500
    assert released == [(500, "remainder")]


def test_late_cancel_skips_release_event_when_release_returns_none(
    client,
    auth_headers,
    bays,
    user_with_plates,
    card,
    monkeypatch,
):
    from app.services import reservation_service

    released: list[tuple[int, str]] = []
    monkeypatch.setattr(
        reservation_service,
        "push_deposit_released",
        lambda *, amount_cents, reason, **_: released.append((amount_cents, reason)),
    )
    monkeypatch.setattr(
        reservation_service.payment_service,
        "release",
        lambda *, reservation_id, reason: None,
    )

    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=5).get_json()
    resp = client.post(
        f"/api/v1/reservations/{created['id']}/cancel",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert released == []


def test_cancel_is_idempotent(client, auth_headers, bays, user_with_plates, card):
    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=45).get_json()
    first = client.post(f"/api/v1/reservations/{created['id']}/cancel", headers=auth_headers)
    second = client.post(f"/api/v1/reservations/{created['id']}/cancel", headers=auth_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Check-in
# ---------------------------------------------------------------------------


def test_check_in_rejected_when_active_no_pi_event_yet(
    client,
    auth_headers,
    bays,
    user_with_plates,
    card,
):
    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=20).get_json()
    resp = client.post(
        f"/api/v1/reservations/{created['id']}/check-in",
        json={"bay_code": "A1", "source": "qr"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "vehicle_not_detected_yet"


def test_check_in_rejects_mismatched_bay_code(
    client,
    auth_headers,
    bays,
    user_with_plates,
    card,
):
    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=20).get_json()
    resp = client.post(
        f"/api/v1/reservations/{created['id']}/check-in",
        json={"bay_code": "A2", "source": "qr"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "bay_code_mismatch"


def test_qr_check_in_succeeds_when_pending(
    client,
    auth_headers,
    bays,
    user_with_plates,
    card,
    app,
):
    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=20).get_json()
    with app.app_context():
        res = db.session.get(Reservation, created["id"])
        res.status = ReservationStatus.PENDING_CHECK_IN
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        bay.state = BayState.PENDING_CHECK_IN
        db.session.commit()

    resp = client.post(
        f"/api/v1/reservations/{created['id']}/check-in",
        json={"bay_code": "A1", "source": "qr"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["status"] == "checked_in"
    assert body["check_in_mechanism"] == "qr"
    assert body["checked_in_at"] is not None


def test_check_in_succeeds_when_in_weak_conflict(
    client,
    auth_headers,
    bays,
    user_with_plates,
    card,
    app,
):
    from app.services import payment_service

    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=20).get_json()
    with app.app_context():
        res = db.session.get(Reservation, created["id"])
        res.status = ReservationStatus.IN_CONFLICT
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        bay.state = BayState.CONFLICT
        db.session.add(
            Conflict(
                bay_id=bay.id,
                reservation_id=res.id,
                kind=ConflictKind.WEAK,
            )
        )
        payment_service.charge_penalty(
            reservation_id=res.id,
            penalty_kind=PenaltyKind.WEAK_CONFLICT,
            amount_cents=500,
        )
        payment_service.release(reservation_id=res.id, reason="remainder")
        db.session.commit()

    resp = client.post(
        f"/api/v1/reservations/{created['id']}/check-in",
        json={"bay_code": "A1", "source": "manual"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["status"] == "checked_in"
    assert body["check_in_mechanism"] == "manual"

    with app.app_context():
        res = db.session.get(Reservation, created["id"])
        assert res.status == ReservationStatus.CHECKED_IN
        conflict = db.session.execute(db.select(Conflict)).scalar_one()
        assert conflict.resolution == ConflictResolution.USER_ARRIVED_AND_CHECKED_IN
        assert conflict.resolved_at is not None
        actions = [row.action for row in db.session.execute(db.select(Payment)).scalars().all()]
        assert PaymentAction.REFUND not in actions


def test_check_in_rejects_strong_conflict(
    client,
    auth_headers,
    bays,
    user_with_plates,
    card,
    app,
):
    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=20).get_json()
    with app.app_context():
        res = db.session.get(Reservation, created["id"])
        res.status = ReservationStatus.IN_CONFLICT
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        bay.state = BayState.CONFLICT
        db.session.add(
            Conflict(
                bay_id=bay.id,
                reservation_id=res.id,
                kind=ConflictKind.STRONG,
                recognised_plate="ZZZ999",
            )
        )
        db.session.commit()

    resp = client.post(
        f"/api/v1/reservations/{created['id']}/check-in",
        json={"bay_code": "A1", "source": "manual"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "reservation_in_conflict"


def test_check_in_rejects_resolved_weak_conflict(
    client,
    auth_headers,
    bays,
    user_with_plates,
    card,
    app,
):
    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=20).get_json()
    with app.app_context():
        res = db.session.get(Reservation, created["id"])
        res.status = ReservationStatus.IN_CONFLICT
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        bay.state = BayState.CONFLICT
        db.session.add(
            Conflict(
                bay_id=bay.id,
                reservation_id=res.id,
                kind=ConflictKind.WEAK,
                resolution=ConflictResolution.VEHICLE_LEFT,
                resolved_at=utcnow(),
            )
        )
        db.session.commit()

    resp = client.post(
        f"/api/v1/reservations/{created['id']}/check-in",
        json={"bay_code": "A1", "source": "manual"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "reservation_in_conflict"


def test_check_in_requires_source_qr_or_manual(
    client,
    auth_headers,
    bays,
    user_with_plates,
    card,
):
    created = _book(client, auth_headers, card, bay_code="A1", in_minutes=20).get_json()
    resp = client.post(
        f"/api/v1/reservations/{created['id']}/check-in",
        json={"bay_code": "A1", "source": "auto_lpr"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Latency (R8)
# ---------------------------------------------------------------------------


def test_end_to_end_latency_under_5_seconds(client, auth_headers, bays, card):
    started = time.monotonic()
    resp = _book(client, auth_headers, card, bay_code="A1", in_minutes=30)
    elapsed = time.monotonic() - started
    assert resp.status_code == 201
    assert elapsed < 5.0


def test_list_reservations_for_user(client, auth_headers, bays, user_with_plates, card):
    _book(client, auth_headers, card, bay_code="A1", in_minutes=20)
    resp = client.get("/api/v1/reservations", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["bay_code"] == "A1"
