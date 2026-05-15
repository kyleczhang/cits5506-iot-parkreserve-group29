"""Strong-conflict recovery: vehicle-left restore + admin termination.

Covers the behaviour added by ``doc/backend/strong-conflict-recovery-plan.zh-CN.md``:

* ``conflict_strong`` is a facility-side incident — no refund, reservation
  stays ``ACTIVE`` / ``CHECKED_IN``.
* ``CONFLICT → AVAILABLE`` with an open strong conflict resolves the
  conflict as ``vehicle_left`` and restores the reservation cache on the Pi.
* The no-show sweeper does not trip on the transient ``AVAILABLE`` because
  the bay mirror is flipped back locally.
* :func:`reservation_service.admin_terminate` is the only path that refunds
  a strong-conflict reservation.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.extensions import db
from app.models import (
    BayEvent,
    BayState,
    CheckInMechanism,
    Conflict,
    ConflictKind,
    ConflictResolution,
    ParkingBay,
    Payment,
    PaymentAction,
    Reservation,
    ReservationStatus,
)
from app.mqtt.topics import PiInboundEventPayload, StatePayload
from app.services import reservation_service
from app.services.bay_service import apply_state
from app.services.event_dispatcher import dispatch_event
from app.utils.time import utcnow

# ---------------------------------------------------------------------------
# helpers (duplicated minimally — these tests are intentionally self-contained
# so failures don't get tangled with the broader event-handler suite)
# ---------------------------------------------------------------------------


def _make_active_reservation(session, *, bay_code: str, user) -> Reservation:
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == bay_code)).scalar_one()
    reservation = Reservation(
        bay_id=bay.id,
        user_id=user.id,
        status=ReservationStatus.ACTIVE,
        expected_arrival_time=utcnow() + timedelta(minutes=10),
    )
    session.add(reservation)
    session.flush()  # populate reservation.id before linking it on the bay
    bay.state = BayState.RESERVED
    bay.current_reservation_id = reservation.id
    session.commit()
    return reservation


def _add_preauth(
    session, reservation: Reservation, mock_card, *, amount_cents: int = 1000
) -> Payment:
    p = Payment(
        reservation_id=reservation.id,
        user_id=reservation.user_id,
        mock_card_id=mock_card.id,
        action=PaymentAction.PRE_AUTH,
        amount_cents=amount_cents,
        idempotency_key=f"pre_auth:{reservation.id}",
    )
    mock_card.balance_cents -= amount_cents
    session.add(p)
    session.commit()
    return p


def _strong_conflict_event(plate: str = "ZZZ999") -> PiInboundEventPayload:
    return PiInboundEventPayload(
        event="conflict_strong",
        ts=utcnow(),
        event_id=uuid4(),
        recognised_plate=plate,
        lpr_confidence=0.91,
    )


def _state(state: str) -> StatePayload:
    return StatePayload(state=state, last_distance_cm=30.0, ts=utcnow(), event_id=uuid4())


# ---------------------------------------------------------------------------
# Vehicle-left restore from ACTIVE
# ---------------------------------------------------------------------------


def test_strong_conflict_cleared_restores_active_reservation(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """The full happy-path: A reserves, wrong car triggers strong conflict,
    wrong car drives away → reservation resumes, no refund."""
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())
        apply_state(bay_code="A1", payload=_state("available"))

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        # Bay mirror was flipped back locally so the sweeper doesn't trip.
        assert bay.state == BayState.RESERVED
        assert bay.current_reservation_id == reservation.id

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.ACTIVE
        assert res.completed_at is None
        assert res.cancelled_at is None

        conflicts = db.session.execute(db.select(Conflict)).scalars().all()
        assert len(conflicts) == 1
        assert conflicts[0].kind == ConflictKind.STRONG
        assert conflicts[0].resolved_at is not None
        assert conflicts[0].resolution == ConflictResolution.VEHICLE_LEFT

        # No refund, no release.
        payments = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(p.action.value for p in payments)
        assert actions == ["pre_auth"]

    # The cache restore went out as a republished `create`, NOT a release.
    assert len(published) == 1
    assert published[0]["bay_code"] == "A1"
    assert published[0]["action"] == "create"
    assert published[0]["reservation"].id == reservation.id
    assert published[0]["user"].id == user_with_plates.id
    assert published[0]["bound_plates"] == ["ABC123", "XYZ789"]
    assert published[0].get("reason") is None


def test_strong_conflict_cleared_restores_checked_in_reservation(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """A is already CHECKED_IN; a wrong vehicle later triggers strong
    conflict and drives away. The CHECKED_IN session resumes."""
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    reservation.status = ReservationStatus.CHECKED_IN
    reservation.checked_in_at = utcnow() - timedelta(minutes=3)
    reservation.check_in_mechanism = CheckInMechanism.AUTO_LPR
    reservation.check_in_recognised_plate = "ABC123"
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.RESERVED_CHECKED_IN
    session.commit()
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())
        apply_state(bay_code="A1", payload=_state("available"))

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.RESERVED_CHECKED_IN
        assert bay.current_reservation_id == reservation.id

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.CHECKED_IN
        assert res.completed_at is None

        conflict = db.session.execute(db.select(Conflict)).scalar_one()
        assert conflict.kind == ConflictKind.STRONG
        assert conflict.resolution == ConflictResolution.VEHICLE_LEFT

        payments = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(p.action.value for p in payments)
        assert actions == ["pre_auth"]

    # Restore command for a CHECKED_IN reservation uses `check_in`, not `create`.
    assert len(published) == 1
    assert published[0]["action"] == "check_in"
    assert published[0]["reservation"].id == reservation.id
    assert published[0]["bound_plates"] == ["ABC123", "XYZ789"]


def test_strong_conflict_cleared_writes_conflict_resolved_audit_row(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    """The audit log gains a CONFLICT_RESOLVED + STATE_CHANGED(AVAILABLE→RESERVED)
    pair instead of the old RESERVATION_COMPLETED row."""
    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())
        apply_state(bay_code="A1", payload=_state("available"))

        kinds = sorted(
            r.kind.value for r in db.session.execute(db.select(BayEvent)).scalars().all()
        )
        # No RESERVATION_COMPLETED row.
        assert "reservation_completed" not in kinds
        assert "conflict_resolved" in kinds


# ---------------------------------------------------------------------------
# Sweeper guard
# ---------------------------------------------------------------------------


def test_sweeper_does_not_no_show_after_strong_conflict_cleared(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """Even with `expected_arrival_time` long past, after a strong-conflict
    clear the reconcile sweeper must NOT synthesise no_show. This locks down
    the "extend the user's arrival window on conflict-clear" decision —
    otherwise the user would be punished for the wrong vehicle's blockage."""
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: None,
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    # Backdate both the booked timestamp and the arrival so the no-show window
    # is already open while still satisfying the booking_window CHECK
    # constraint (expected_arrival_time must be within 1h of booked_at).
    booked = utcnow() - timedelta(minutes=50)
    reservation.booked_at = booked
    reservation.expected_arrival_time = booked + timedelta(minutes=20)
    session.commit()
    _add_preauth(session, reservation, mock_cards[0])

    from app.jobs import reconcile_reservations

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())
        apply_state(bay_code="A1", payload=_state("available"))

        # Direct invariant — the implementation decision under test.
        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.RESERVED

        result = reconcile_reservations.run_once()
        assert result == {"no_show": 0, "conflict_weak": 0}

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.ACTIVE

        payments = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(p.action.value for p in payments)
        assert actions == ["pre_auth"]


# ---------------------------------------------------------------------------
# Admin termination — the only refund path for a strong-conflict reservation
# ---------------------------------------------------------------------------


def test_admin_terminate_during_strong_conflict_refunds_and_releases(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    admin,
    monkeypatch,
):
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.reservation_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())

        reservation_service.admin_terminate(admin=admin, reservation_id=reservation.id)

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.CANCELLED
        assert res.cancelled_at is not None

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        # Bay mirror stays CONFLICT — the wrong vehicle is still physically
        # present, so flipping AVAILABLE here would advertise a phantom free
        # bay. Pi's next /state will reconcile when the wrong vehicle leaves.
        assert bay.state == BayState.CONFLICT
        assert bay.current_reservation_id is None

        conflict = db.session.execute(db.select(Conflict)).scalar_one()
        assert conflict.resolution == ConflictResolution.ADMIN_RESOLVED
        assert conflict.resolved_at is not None

        # Conflict-resolved audit row is recorded.
        kinds = [
            r.kind.value for r in db.session.execute(db.select(BayEvent)).scalars().all()
        ]
        assert "conflict_resolved" in kinds

        payments = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(p.action.value for p in payments)
        assert actions == ["pre_auth", "refund"]
        refund = next(p for p in payments if p.action == PaymentAction.REFUND)
        assert refund.amount_cents == 1000

    assert len(published) == 1
    assert published[0]["bay_code"] == "A1"
    assert published[0]["action"] == "release"
    assert published[0]["reason"] == "admin_override"
    assert published[0]["reservation"].id == reservation.id


def test_admin_terminate_during_strong_conflict_does_not_open_booking_window(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    admin,
    monkeypatch,
):
    """The bug this test pins: previously admin_terminate flipped CONFLICT
    → AVAILABLE while the wrong vehicle was still parked, so a fresh
    booking attempt would slip through ``_assert_bay_reservable`` and stack
    a second reservation on a physically blocked bay. Now the strong
    conflict keeps the bay non-reservable until the Pi reports it free."""
    monkeypatch.setattr(
        "app.services.reservation_service.publish_reservation_command",
        lambda **kwargs: None,
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())
        reservation_service.admin_terminate(admin=admin, reservation_id=reservation.id)

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        # _assert_bay_reservable rejects CONFLICT → fresh bookings blocked.
        from app.utils.errors import ConflictError

        try:
            reservation_service._assert_bay_reservable(bay)
        except ConflictError as exc:
            assert exc.code == "bay_not_available"
        else:
            raise AssertionError("CONFLICT bay should not pass _assert_bay_reservable")


def test_admin_terminate_during_weak_conflict_flips_bay_available(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    admin,
    monkeypatch,
):
    """Weak conflict has no third-party vehicle present (it's a deferred
    holder breach). admin_terminate may safely flip the mirror to AVAILABLE."""
    from datetime import timedelta

    from app.models import ConflictKind

    monkeypatch.setattr(
        "app.services.reservation_service.publish_reservation_command",
        lambda **kwargs: None,
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.CONFLICT
    weak = Conflict(
        bay_id=bay.id,
        reservation_id=reservation.id,
        kind=ConflictKind.WEAK,
        source_event_id=uuid4(),
        detected_at=utcnow() - timedelta(seconds=30),
    )
    session.add(weak)
    session.commit()

    with app.app_context():
        reservation_service.admin_terminate(admin=admin, reservation_id=reservation.id)

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.AVAILABLE
        assert bay.current_reservation_id is None
        weak = db.session.get(Conflict, weak.id)
        assert weak.resolved_at is not None
        assert weak.resolution == ConflictResolution.ADMIN_RESOLVED


def test_admin_terminate_cleans_orphan_conflict_on_terminal_reservation(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    admin,
    monkeypatch,
):
    """If the holder cancels first via the no-fault path... wait, the
    no-fault cancel branch resolves the conflict itself. The orphan case
    targeted here is older, tighter: a reservation that reached a terminal
    status by some other path (e.g. a future bug, or a hand-edited row)
    while leaving an unresolved conflict. admin_terminate must still close
    the conflict so the partial unique index doesn't trap the bay."""
    monkeypatch.setattr(
        "app.services.reservation_service.publish_reservation_command",
        lambda **kwargs: None,
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    # Simulate a "stuck" reservation: terminal status, but an unresolved
    # strong conflict still attached to the bay.
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = utcnow()
    bay.current_reservation_id = None
    bay.state = BayState.CONFLICT
    orphan = Conflict(
        bay_id=bay.id,
        reservation_id=reservation.id,
        kind=ConflictKind.STRONG,
        recognised_plate="ZZZ999",
        source_event_id=uuid4(),
        detected_at=utcnow(),
    )
    session.add(orphan)
    session.commit()

    with app.app_context():
        reservation_service.admin_terminate(admin=admin, reservation_id=reservation.id)

        orphan = db.session.get(Conflict, orphan.id)
        assert orphan.resolved_at is not None
        assert orphan.resolution == ConflictResolution.ADMIN_RESOLVED

        # Reservation status was already terminal; admin_terminate must NOT
        # mutate it again or issue a second refund.
        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.CANCELLED

        payments = db.session.execute(db.select(Payment)).scalars().all()
        assert sorted(p.action.value for p in payments) == ["pre_auth"]


def test_admin_terminate_terminal_with_no_open_conflict_short_circuits(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    admin,
    monkeypatch,
):
    """True idempotent no-op: terminal reservation, no open conflict."""
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.reservation_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        reservation_service.admin_terminate(admin=admin, reservation_id=reservation.id)
        reservation_service.admin_terminate(admin=admin, reservation_id=reservation.id)

        refunds = (
            db.session.execute(db.select(Payment).where(Payment.action == PaymentAction.REFUND))
            .scalars()
            .all()
        )
        assert len(refunds) == 1

    assert len(published) == 1


# ---------------------------------------------------------------------------
# User-cancel under strong conflict — no-fault refund branch
# ---------------------------------------------------------------------------


def test_cancel_under_strong_conflict_refunds_and_resolves_conflict(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """Holder cancels while the wrong vehicle still occupies the bay.
    Must NOT charge a late_cancel penalty, MUST refund in full, MUST
    close the open conflict as USER_CANCELLED, and MUST leave bay.state
    untouched (the wrong vehicle is still physically there)."""
    from datetime import timedelta

    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.reservation_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    # Within the late-cancel cutoff window — proves we DID NOT take the
    # late-cancel branch (which would charge a penalty).
    reservation.expected_arrival_time = utcnow() + timedelta(minutes=2)
    session.commit()
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())

        reservation_service.cancel(user=user_with_plates, reservation_id=reservation.id)

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.CANCELLED  # not CANCELLED_LATE
        assert res.cancelled_at is not None

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.CONFLICT  # untouched
        assert bay.current_reservation_id is None

        conflict = db.session.execute(db.select(Conflict)).scalar_one()
        assert conflict.resolved_at is not None
        assert conflict.resolution == ConflictResolution.USER_CANCELLED

        # Payment ledger: pre_auth + refund only — no penalty_capture.
        payments = db.session.execute(db.select(Payment)).scalars().all()
        actions = sorted(p.action.value for p in payments)
        assert actions == ["pre_auth", "refund"]
        refund = next(p for p in payments if p.action == PaymentAction.REFUND)
        assert refund.amount_cents == 1000

        # Both the cancel + conflict_resolved audit rows are emitted.
        kinds = [
            r.kind.value for r in db.session.execute(db.select(BayEvent)).scalars().all()
        ]
        assert "reservation_cancelled" in kinds
        assert "conflict_resolved" in kinds

    # Pi gets a release with the same admin_override reason as facility
    # termination — this is, semantically, a facility-incident teardown.
    assert len(published) == 1
    assert published[0]["action"] == "release"
    assert published[0]["reason"] == "admin_override"


def test_cancel_after_strong_conflict_does_not_trip_no_show_sweeper(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """After the no-fault cancel, the reservation is CANCELLED so the
    sweeper can't synthesise no_show on it (status filter rejects), and
    the conflict is already resolved so the bay can heal cleanly when
    the wrong vehicle leaves."""
    monkeypatch.setattr(
        "app.services.reservation_service.publish_reservation_command",
        lambda **kwargs: None,
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())
        reservation_service.cancel(user=user_with_plates, reservation_id=reservation.id)

        # Wrong vehicle eventually drives off — Pi reports CONFLICT → AVAILABLE.
        # No restore (conflict already resolved), no completion (reservation
        # already terminal). Bay just mirrors AVAILABLE.
        apply_state(bay_code="A1", payload=_state("available"))

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.AVAILABLE

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.CANCELLED
        assert res.completed_at is None  # wasn't promoted to COMPLETED

        # Still just pre_auth + refund — no spurious release/penalty.
        payments = db.session.execute(db.select(Payment)).scalars().all()
        assert sorted(p.action.value for p in payments) == ["pre_auth", "refund"]


def test_cancel_without_strong_conflict_still_uses_late_cancel_path(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """Regression guard: the no-fault branch must only fire when an open
    *strong* conflict exists. Plain late cancels still charge the penalty."""
    from datetime import timedelta

    monkeypatch.setattr(
        "app.services.reservation_service.publish_reservation_command",
        lambda **kwargs: None,
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    reservation.expected_arrival_time = utcnow() + timedelta(minutes=2)  # < 15-min cutoff
    session.commit()
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        reservation_service.cancel(user=user_with_plates, reservation_id=reservation.id)

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.CANCELLED_LATE

        actions = sorted(
            p.action.value for p in db.session.execute(db.select(Payment)).scalars().all()
        )
        # late_cancel penalty captured, then remainder released.
        assert "penalty_capture" in actions
        assert "release" in actions


def test_admin_terminate_is_idempotent_on_terminal_reservation(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    admin,
    monkeypatch,
):
    """A second admin_terminate on an already-cancelled reservation is a
    no-op — no double refund, no second release publish."""
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.reservation_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        reservation_service.admin_terminate(admin=admin, reservation_id=reservation.id)
        reservation_service.admin_terminate(admin=admin, reservation_id=reservation.id)

        refunds = (
            db.session.execute(db.select(Payment).where(Payment.action == PaymentAction.REFUND))
            .scalars()
            .all()
        )
        assert len(refunds) == 1

    # publish fired only on the first call; the second short-circuits.
    assert len(published) == 1


def test_admin_terminate_rejects_non_admin_caller(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
):
    from app.utils.errors import ForbiddenError

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        try:
            reservation_service.admin_terminate(
                admin=user_with_plates,
                reservation_id=reservation.id,
            )
        except ForbiddenError as exc:
            assert exc.code == "admin_only"
        else:
            raise AssertionError("expected ForbiddenError")


# ---------------------------------------------------------------------------
# Restore branch refuses to fire when it shouldn't
# ---------------------------------------------------------------------------


def test_strong_conflict_cleared_without_open_reservation_does_not_restore(
    app,
    session,
    bays,
    monkeypatch,
):
    """If conflict_strong fires on a bay with no open reservation, clearing
    the bay must NOT invent a reservation and must NOT publish anything.
    Without a reservation to anchor against, the strong conflict simply
    sits open — admin disposition required."""
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())
        apply_state(bay_code="A1", payload=_state("available"))

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        # No reservation to restore → bay stays AVAILABLE.
        assert bay.state == BayState.AVAILABLE

        # Conflict stays open (no resumable reservation; nothing to restore).
        conflicts = db.session.execute(db.select(Conflict)).scalars().all()
        assert len(conflicts) == 1
        assert conflicts[0].resolved_at is None

    assert published == []


def test_conflict_to_available_does_not_complete_strong_active_reservation(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """Direct regression for the original bug: with old state CONFLICT, an
    open strong conflict, and an open ACTIVE reservation, Pi reporting
    AVAILABLE must NOT mark the reservation COMPLETED or issue a release /
    refund — those are the symptoms the recovery plan is fixing."""
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: None,
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())
        apply_state(bay_code="A1", payload=_state("available"))

        res = db.session.get(Reservation, reservation.id)
        assert res.status != ReservationStatus.COMPLETED
        assert res.completed_at is None

        kinds = {r.kind.value for r in db.session.execute(db.select(BayEvent)).scalars().all()}
        assert "reservation_completed" not in kinds

        actions = sorted(
            r.action.value for r in db.session.execute(db.select(Payment)).scalars().all()
        )
        assert "release" not in actions
        assert "refund" not in actions


# ---------------------------------------------------------------------------
# Pi-skipped AVAILABLE and lost conflict_strong event
# ---------------------------------------------------------------------------


def test_strong_conflict_cleared_via_direct_reserved_transition(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """Pi may report CONFLICT → RESERVED directly (no transient AVAILABLE).
    The strong-restore path must still resolve the conflict and resume the
    reservation."""
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])

    with app.app_context():
        dispatch_event(bay_code="A1", payload=_strong_conflict_event())
        # Skip AVAILABLE — Pi jumps straight back to RESERVED.
        apply_state(bay_code="A1", payload=_state("reserved"))

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.RESERVED

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.ACTIVE
        assert res.completed_at is None

        conflict = db.session.execute(db.select(Conflict)).scalar_one()
        assert conflict.resolution == ConflictResolution.VEHICLE_LEFT

    assert len(published) == 1
    assert published[0]["action"] == "create"
    assert published[0]["reservation"].id == reservation.id


def test_strong_conflict_cleared_defends_pending_check_in_when_event_lost(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """If the conflict_strong event was dropped or arrived out of order so
    the reservation is still PENDING_CHECK_IN when the wrong vehicle leaves,
    the restore path must still roll it back to ACTIVE."""
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])
    # Simulate the desync: reservation is PENDING_CHECK_IN, bay is CONFLICT,
    # and an open strong conflict row already exists — exactly the state we
    # would land in if the conflict_strong dispatcher had crashed mid-handler.
    reservation.status = ReservationStatus.PENDING_CHECK_IN
    reservation.check_in_grace_expires_at = utcnow() + timedelta(minutes=5)
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.CONFLICT
    session.add(
        Conflict(
            bay_id=bay.id,
            reservation_id=reservation.id,
            kind=ConflictKind.STRONG,
            source_event_id=uuid4(),
            detected_at=utcnow(),
            recognised_plate="ZZZ999",
        )
    )
    session.commit()

    with app.app_context():
        apply_state(bay_code="A1", payload=_state("available"))

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.ACTIVE
        assert res.check_in_grace_expires_at is None

        conflict = db.session.execute(db.select(Conflict)).scalar_one()
        assert conflict.resolution == ConflictResolution.VEHICLE_LEFT

    assert len(published) == 1
    assert published[0]["action"] == "create"


# ---------------------------------------------------------------------------
# No-conflict pending_check_in rollback
# ---------------------------------------------------------------------------


def test_pending_check_in_to_reserved_rolls_back_to_active(
    app,
    session,
    bays,
    user_with_plates,
    mock_cards,
    monkeypatch,
):
    """An unknown vehicle visited the bay (so the Pi raised pending_check_in)
    but left before LPR ever fired conflict_strong. The bay returns directly
    to RESERVED — the reservation must roll back to ACTIVE instead of
    staying stuck in PENDING_CHECK_IN."""
    published: list[dict] = []
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: published.append(kwargs),
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    _add_preauth(session, reservation, mock_cards[0])
    reservation.status = ReservationStatus.PENDING_CHECK_IN
    reservation.check_in_grace_expires_at = utcnow() + timedelta(minutes=5)
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.PENDING_CHECK_IN
    session.commit()

    with app.app_context():
        apply_state(bay_code="A1", payload=_state("reserved"))

        bay = db.session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
        assert bay.state == BayState.RESERVED

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.ACTIVE
        assert res.check_in_grace_expires_at is None
        assert res.completed_at is None

        # No conflict rows manufactured — there was never a conflict_strong.
        conflicts = db.session.execute(db.select(Conflict)).scalars().all()
        assert conflicts == []

        # No release / refund — the reservation is still live.
        actions = sorted(
            p.action.value for p in db.session.execute(db.select(Payment)).scalars().all()
        )
        assert actions == ["pre_auth"]

    assert len(published) == 1
    assert published[0]["bay_code"] == "A1"
    assert published[0]["action"] == "create"
    assert published[0]["reservation"].id == reservation.id
    assert published[0]["bound_plates"] == ["ABC123", "XYZ789"]


def test_pending_check_in_to_available_still_completes(
    app,
    session,
    bays,
    user_with_plates,
    monkeypatch,
):
    """Guard: PENDING_CHECK_IN → AVAILABLE remains the completion path. The
    new rollback helper must not fire on this transition."""
    monkeypatch.setattr(
        "app.services.bay_service.publish_reservation_command",
        lambda **kwargs: None,
    )

    reservation = _make_active_reservation(session, bay_code="A1", user=user_with_plates)
    reservation.status = ReservationStatus.PENDING_CHECK_IN
    reservation.check_in_grace_expires_at = utcnow() + timedelta(minutes=5)
    bay = session.execute(db.select(ParkingBay).where(ParkingBay.code == "A1")).scalar_one()
    bay.state = BayState.PENDING_CHECK_IN
    session.commit()

    with app.app_context():
        apply_state(bay_code="A1", payload=_state("available"))

        res = db.session.get(Reservation, reservation.id)
        assert res.status == ReservationStatus.COMPLETED
