"""Seed data declarations.

Keep this file limited to record declarations and light grouping. ``seed.py``
owns the actual persistence logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import (
    BayState,
    CheckInMechanism,
    PaymentAction,
    PaymentStatus,
    PenaltyKind,
    ReservationStatus,
    UserRole,
)


def _pre_auth_key(reservation_id: str) -> str:
    """Return the canonical idempotency key for a reservation pre-auth row."""

    return f"pre_auth:{reservation_id}"


def _release_key(reservation_id: str, reason: str) -> str:
    """Return the canonical idempotency key for a release row."""

    return f"release:{reservation_id}:{reason}"


def _penalty_key(reservation_id: str, penalty_kind: PenaltyKind) -> str:
    """Return the canonical idempotency key for a penalty-capture row."""

    return f"penalty_capture:{reservation_id}:{penalty_kind.value}"


def _refund_key(reservation_id: str) -> str:
    """Return the canonical idempotency key for a strong-conflict refund row."""

    return f"refund:{reservation_id}:strong_conflict"


@dataclass(frozen=True)
class ParkingBaySeed:
    """Static seed declaration for one physical bay."""

    code: str
    label: str
    device_id: str
    state: BayState = BayState.AVAILABLE


@dataclass(frozen=True)
class UserSeed:
    """Static user-account seed."""

    email: str
    name: str
    password: str
    role: UserRole
    plates: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MockCardSeed:
    """Static mock-bank card seed tied to a named demo user."""

    card_number: str
    cvv: str
    holder_name: str
    expiry_month: int
    expiry_year: int
    balance_cents: int


@dataclass(frozen=True)
class PaymentSeed:
    """Relative-time payment ledger seed for one reservation scenario.

    ``occurred_offset_minutes`` is interpreted relative to the moment the seed
    command runs, so history scenarios stay fresh across repeated demo runs.
    """

    idempotency_key: str
    card_number: str
    action: PaymentAction
    amount_cents: int
    occurred_offset_minutes: int
    status: PaymentStatus = PaymentStatus.SUCCEEDED
    penalty_kind: PenaltyKind | None = None
    source_event_id: str | None = None


@dataclass(frozen=True)
class ReservationSeed:
    """Relative-time reservation scenario definition.

    The offsets here are intentionally *not* absolute timestamps. ``seed.py``
    resolves them from a single captured ``now`` so the scenario remains
    logically consistent every time the database is re-seeded.
    """

    id: str
    user_email: str
    bay_code: str
    status: ReservationStatus
    expected_arrival_offset_minutes: int
    booked_offset_minutes: int
    payments: tuple[PaymentSeed, ...]
    bay_state: BayState | None = None
    attach_to_bay: bool = False
    check_in_grace_offset_minutes: int | None = None
    checked_in_offset_minutes: int | None = None
    cancelled_offset_minutes: int | None = None
    completed_offset_minutes: int | None = None
    check_in_mechanism: CheckInMechanism | None = None
    check_in_recognised_plate: str | None = None


@dataclass(frozen=True)
class SeedDataset:
    """Named bundle of seed records applied together from the CLI."""

    name: str
    description: str
    bays: tuple[ParkingBaySeed, ...] = field(default_factory=tuple)
    users: tuple[UserSeed, ...] = field(default_factory=tuple)
    mock_cards: tuple[MockCardSeed, ...] = field(default_factory=tuple)
    reservations: tuple[ReservationSeed, ...] = field(default_factory=tuple)


# Stable identifiers keep scenario references deterministic across seed runs.
READY_RESERVATION_ID = "00000000-0000-0000-0000-00000000a101"
CONFLICT_RESERVATION_ID = "00000000-0000-0000-0000-00000000a202"
CHECKED_IN_RESERVATION_ID = "00000000-0000-0000-0000-00000000a303"
COMPLETED_HISTORY_RESERVATION_ID = "00000000-0000-0000-0000-00000000b101"
LATE_CANCEL_HISTORY_RESERVATION_ID = "00000000-0000-0000-0000-00000000b202"
NO_SHOW_HISTORY_RESERVATION_ID = "00000000-0000-0000-0000-00000000b303"
REFUND_HISTORY_RESERVATION_ID = "00000000-0000-0000-0000-00000000b404"


DEMO_DATASET = SeedDataset(
    name="demo",
    description="Three available bays, five fixed user accounts, and account-matched demo mock-bank cards.",
    bays=(
        ParkingBaySeed(code="A1", label="Bay A1", device_id="esp32-a1"),
        ParkingBaySeed(code="A2", label="Bay A2", device_id="esp32-a2"),
        ParkingBaySeed(code="A3", label="Bay A3", device_id="esp32-a3"),
    ),
    users=(
        UserSeed(
            email="nyx@parkreserve.local",
            name="Nyx Chen",
            password="nyxParkreserve29!",
            role=UserRole.USER,
            plates=(
                ("ABC123", "Daily Driver"),
                ("NYX888", "Spare Hatch"),
            ),
        ),
        UserSeed(
            email="riya@parkreserve.local",
            name="Riya Sakhiya",
            password="riyaParkreserve29!",
            role=UserRole.USER,
            plates=(("RIYA29", "Campus Car"),),
        ),
        UserSeed(
            email="yuan@parkreserve.local",
            name="Yuan Cong",
            password="yuanParkreserve29!",
            role=UserRole.USER,
        ),
        UserSeed(
            email="cheng@parkreserve.local",
            name="Cheng Zhang",
            password="chengParkreserve29!",
            role=UserRole.USER,
            plates=(
                ("CZH5506", "Daily Driver"),
                ("PARK29", "Partner Car"),
            ),
        ),
        UserSeed(
            email="admin@parkreserve.local",
            name="Admin User",
            password="adminParkreserve29!",
            role=UserRole.ADMIN,
        ),
    ),
    mock_cards=(
        MockCardSeed(
            card_number="4111111111111001",
            cvv="123",
            holder_name="Nyx Chen",
            expiry_month=12,
            expiry_year=2030,
            balance_cents=150_00,
        ),
        MockCardSeed(
            card_number="4111111111111002",
            cvv="234",
            holder_name="Nyx Chen",
            expiry_month=12,
            expiry_year=2030,
            balance_cents=8_00,
        ),
        MockCardSeed(
            card_number="4222222222222001",
            cvv="345",
            holder_name="Riya Sakhiya",
            expiry_month=12,
            expiry_year=2030,
            balance_cents=120_00,
        ),
        MockCardSeed(
            card_number="4222222222222002",
            cvv="456",
            holder_name="Riya Sakhiya",
            expiry_month=12,
            expiry_year=2030,
            balance_cents=0,
        ),
        MockCardSeed(
            card_number="4333333333333001",
            cvv="111",
            holder_name="Yuan Cong",
            expiry_month=11,
            expiry_year=2031,
            balance_cents=300_00,
        ),
        MockCardSeed(
            card_number="4333333333333002",
            cvv="222",
            holder_name="Yuan Cong",
            expiry_month=1,
            expiry_year=2024,
            balance_cents=80_00,
        ),
        MockCardSeed(
            card_number="4444444444444001",
            cvv="333",
            holder_name="Cheng Zhang",
            expiry_month=10,
            expiry_year=2031,
            balance_cents=180_00,
        ),
        MockCardSeed(
            card_number="4444444444444002",
            cvv="444",
            holder_name="Cheng Zhang",
            expiry_month=10,
            expiry_year=2031,
            balance_cents=60_00,
        ),
        MockCardSeed(
            card_number="4555555555555001",
            cvv="555",
            holder_name="Admin User",
            expiry_month=9,
            expiry_year=2032,
            balance_cents=500_00,
        ),
        MockCardSeed(
            card_number="4555555555555002",
            cvv="666",
            holder_name="Admin User",
            expiry_month=9,
            expiry_year=2032,
            balance_cents=75_00,
        ),
    ),
)


# This scenario is the shortest path for end-to-end booking / arrival demos.
INTEGRATION_READY_DATASET = SeedDataset(
    name="integration_ready",
    description="One future reservation on A1 for Nyx using plate ABC123; ready for reserve -> auto_check_in / no_show demos.",
    reservations=(
        ReservationSeed(
            id=READY_RESERVATION_ID,
            user_email="nyx@parkreserve.local",
            bay_code="A1",
            status=ReservationStatus.ACTIVE,
            expected_arrival_offset_minutes=20,
            booked_offset_minutes=-10,
            bay_state=BayState.RESERVED,
            attach_to_bay=True,
            payments=(
                PaymentSeed(
                    idempotency_key=_pre_auth_key(READY_RESERVATION_ID),
                    card_number="4111111111111001",
                    action=PaymentAction.PRE_AUTH,
                    amount_cents=1000,
                    occurred_offset_minutes=-10,
                ),
            ),
        ),
    ),
)


# This one is tuned to reproduce a strong conflict using the publisher defaults.
INTEGRATION_CONFLICT_DATASET = SeedDataset(
    name="integration_conflict",
    description="One pending-check-in reservation on A2 for Cheng; publisher default plate ABC123 will reproduce a strong conflict.",
    reservations=(
        ReservationSeed(
            id=CONFLICT_RESERVATION_ID,
            user_email="cheng@parkreserve.local",
            bay_code="A2",
            status=ReservationStatus.PENDING_CHECK_IN,
            expected_arrival_offset_minutes=-2,
            booked_offset_minutes=-18,
            bay_state=BayState.PENDING_CHECK_IN,
            attach_to_bay=True,
            check_in_grace_offset_minutes=3,
            payments=(
                PaymentSeed(
                    idempotency_key=_pre_auth_key(CONFLICT_RESERVATION_ID),
                    card_number="4444444444444001",
                    action=PaymentAction.PRE_AUTH,
                    amount_cents=1000,
                    occurred_offset_minutes=-18,
                ),
            ),
        ),
    ),
)


# This keeps one session already inside the parking flow for exit-path demos.
INTEGRATION_CHECKED_IN_DATASET = SeedDataset(
    name="integration_checked_in",
    description="One checked-in reservation on A3 for Riya; ready to test leave-bay completion and deposit release.",
    reservations=(
        ReservationSeed(
            id=CHECKED_IN_RESERVATION_ID,
            user_email="riya@parkreserve.local",
            bay_code="A3",
            status=ReservationStatus.CHECKED_IN,
            expected_arrival_offset_minutes=-6,
            booked_offset_minutes=-25,
            bay_state=BayState.RESERVED_CHECKED_IN,
            attach_to_bay=True,
            checked_in_offset_minutes=-4,
            check_in_mechanism=CheckInMechanism.AUTO_LPR,
            check_in_recognised_plate="RIYA29",
            payments=(
                PaymentSeed(
                    idempotency_key=_pre_auth_key(CHECKED_IN_RESERVATION_ID),
                    card_number="4222222222222001",
                    action=PaymentAction.PRE_AUTH,
                    amount_cents=1000,
                    occurred_offset_minutes=-25,
                ),
            ),
        ),
    ),
)


# This bundle exists for payment-history screens and receipt-style demos.
PAYMENTS_HISTORY_DATASET = SeedDataset(
    name="payments_history",
    description="Closed reservations covering release, late-cancel penalty, no-show penalty, and strong-conflict refund history.",
    reservations=(
        ReservationSeed(
            id=COMPLETED_HISTORY_RESERVATION_ID,
            user_email="yuan@parkreserve.local",
            bay_code="A1",
            status=ReservationStatus.COMPLETED,
            expected_arrival_offset_minutes=-270,
            booked_offset_minutes=-300,
            checked_in_offset_minutes=-268,
            completed_offset_minutes=-240,
            check_in_mechanism=CheckInMechanism.MANUAL,
            payments=(
                PaymentSeed(
                    idempotency_key=_pre_auth_key(COMPLETED_HISTORY_RESERVATION_ID),
                    card_number="4333333333333001",
                    action=PaymentAction.PRE_AUTH,
                    amount_cents=1000,
                    occurred_offset_minutes=-300,
                ),
                PaymentSeed(
                    idempotency_key=_release_key(COMPLETED_HISTORY_RESERVATION_ID, "completed"),
                    card_number="4333333333333001",
                    action=PaymentAction.RELEASE,
                    amount_cents=1000,
                    occurred_offset_minutes=-240,
                ),
            ),
        ),
        ReservationSeed(
            id=LATE_CANCEL_HISTORY_RESERVATION_ID,
            user_email="cheng@parkreserve.local",
            bay_code="A2",
            status=ReservationStatus.CANCELLED_LATE,
            expected_arrival_offset_minutes=-200,
            booked_offset_minutes=-220,
            cancelled_offset_minutes=-203,
            payments=(
                PaymentSeed(
                    idempotency_key=_pre_auth_key(LATE_CANCEL_HISTORY_RESERVATION_ID),
                    card_number="4444444444444002",
                    action=PaymentAction.PRE_AUTH,
                    amount_cents=1000,
                    occurred_offset_minutes=-220,
                ),
                PaymentSeed(
                    idempotency_key=_penalty_key(
                        LATE_CANCEL_HISTORY_RESERVATION_ID, PenaltyKind.LATE_CANCEL
                    ),
                    card_number="4444444444444002",
                    action=PaymentAction.PENALTY_CAPTURE,
                    penalty_kind=PenaltyKind.LATE_CANCEL,
                    amount_cents=500,
                    occurred_offset_minutes=-203,
                ),
                PaymentSeed(
                    idempotency_key=_release_key(LATE_CANCEL_HISTORY_RESERVATION_ID, "remainder"),
                    card_number="4444444444444002",
                    action=PaymentAction.RELEASE,
                    amount_cents=500,
                    occurred_offset_minutes=-202,
                ),
            ),
        ),
        ReservationSeed(
            id=NO_SHOW_HISTORY_RESERVATION_ID,
            user_email="admin@parkreserve.local",
            bay_code="A3",
            status=ReservationStatus.EXPIRED_NO_SHOW,
            expected_arrival_offset_minutes=-140,
            booked_offset_minutes=-170,
            payments=(
                PaymentSeed(
                    idempotency_key=_pre_auth_key(NO_SHOW_HISTORY_RESERVATION_ID),
                    card_number="4555555555555001",
                    action=PaymentAction.PRE_AUTH,
                    amount_cents=1000,
                    occurred_offset_minutes=-170,
                ),
                PaymentSeed(
                    idempotency_key=_penalty_key(
                        NO_SHOW_HISTORY_RESERVATION_ID, PenaltyKind.NO_SHOW
                    ),
                    card_number="4555555555555001",
                    action=PaymentAction.PENALTY_CAPTURE,
                    penalty_kind=PenaltyKind.NO_SHOW,
                    amount_cents=500,
                    occurred_offset_minutes=-134,
                ),
                PaymentSeed(
                    idempotency_key=_release_key(NO_SHOW_HISTORY_RESERVATION_ID, "remainder"),
                    card_number="4555555555555001",
                    action=PaymentAction.RELEASE,
                    amount_cents=500,
                    occurred_offset_minutes=-133,
                ),
            ),
        ),
        ReservationSeed(
            id=REFUND_HISTORY_RESERVATION_ID,
            user_email="admin@parkreserve.local",
            bay_code="A2",
            status=ReservationStatus.IN_CONFLICT,
            expected_arrival_offset_minutes=-90,
            booked_offset_minutes=-120,
            payments=(
                PaymentSeed(
                    idempotency_key=_pre_auth_key(REFUND_HISTORY_RESERVATION_ID),
                    card_number="4555555555555002",
                    action=PaymentAction.PRE_AUTH,
                    amount_cents=1000,
                    occurred_offset_minutes=-120,
                ),
                PaymentSeed(
                    idempotency_key=_refund_key(REFUND_HISTORY_RESERVATION_ID),
                    card_number="4555555555555002",
                    action=PaymentAction.REFUND,
                    amount_cents=1000,
                    occurred_offset_minutes=-88,
                ),
            ),
        ),
    ),
)


# Base datasets define the stable starting point for a seed run.
BASE_DATASETS = {
    DEMO_DATASET.name: DEMO_DATASET,
}

# Scenario datasets add reservations/payment history on top of a base dataset.
SCENARIO_DATASETS = {
    INTEGRATION_READY_DATASET.name: INTEGRATION_READY_DATASET,
    INTEGRATION_CONFLICT_DATASET.name: INTEGRATION_CONFLICT_DATASET,
    INTEGRATION_CHECKED_IN_DATASET.name: INTEGRATION_CHECKED_IN_DATASET,
    PAYMENTS_HISTORY_DATASET.name: PAYMENTS_HISTORY_DATASET,
}

DATASETS = {
    **BASE_DATASETS,
    **SCENARIO_DATASETS,
}

DEFAULT_DATASET_NAMES = (DEMO_DATASET.name,)
