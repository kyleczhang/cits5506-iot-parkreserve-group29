"""Seed runner for demo and scenario records.

This script stays as the stable execution entrypoint used by ``make seed``.
The concrete rows live in ``scripts/seed_data.py`` so future additions only
need data edits, not more persistence code here.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db
from app.models import LicencePlate, MockCard, ParkingBay, Payment, PaymentAction, Reservation, User
from app.utils import plate as plate_utils
from app.utils.security import hash_password
from app.utils.time import utcnow
from scripts.seed_data import (
    BASE_DATASETS,
    DATASETS,
    DEFAULT_DATASET_NAMES,
    MockCardSeed,
    ParkingBaySeed,
    PaymentSeed,
    ReservationSeed,
    SCENARIO_DATASETS,
    SeedDataset,
    UserSeed,
)


@dataclass
class SeedStats:
    """Counters reported after one seed run."""

    bays_created: int = 0
    users_created: int = 0
    plates_created: int = 0
    mock_cards_created: int = 0
    reservations_created: int = 0
    payments_created: int = 0

    def summary(self) -> str:
        """Return the compact CLI summary shown at the end of seeding."""

        return (
            f"bays={self.bays_created}, "
            f"users={self.users_created}, "
            f"plates={self.plates_created}, "
            f"mock_cards={self.mock_cards_created}, "
            f"reservations={self.reservations_created}, "
            f"payments={self.payments_created}"
        )


def _parse_args() -> argparse.Namespace:
    """Parse the small CLI surface used by ``make seed`` and manual runs."""

    parser = argparse.ArgumentParser(description="Seed ParkReserve demo data.")
    parser.add_argument(
        "--dataset",
        action="append",
        dest="datasets",
        metavar="NAME",
        help=(
            "Dataset name to apply. Repeat the flag to combine datasets. "
            "Defaults to the configured base set."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available datasets and exit.",
    )
    return parser.parse_args()


def _selected_datasets(names: list[str] | None) -> list[SeedDataset]:
    """Resolve CLI dataset names into concrete datasets.

    Base datasets provide the stable rows every run starts from. Scenario
    datasets layer reservation/payment situations on top of that base.
    """

    requested = list(dict.fromkeys(names or DEFAULT_DATASET_NAMES))
    unknown = [name for name in requested if name not in DATASETS]
    if unknown:
        available = ", ".join(sorted(DATASETS))
        missing = ", ".join(unknown)
        raise SystemExit(f"unknown dataset(s): {missing}. available: {available}")

    base_names = [name for name in requested if name in BASE_DATASETS]
    scenario_names = [name for name in requested if name in SCENARIO_DATASETS]
    if scenario_names and not base_names:
        base_names = list(DEFAULT_DATASET_NAMES)

    selected_names = list(dict.fromkeys([*base_names, *scenario_names]))
    return [DATASETS[name] for name in selected_names]


def _reset_seed_tables() -> None:
    """Clear application tables so every seed run rebuilds a known state."""

    table_names = ", ".join(table.name for table in db.metadata.sorted_tables)
    if not table_names:
        return

    db.session.flush()
    db.session.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    db.session.expunge_all()


def _planned_card_balances(datasets: list[SeedDataset]) -> dict[str, int]:
    """Resolve final mock-card balances before inserts happen.

    The seed stays insert-only by computing the balance implied by all selected
    payment rows up front, then inserting each mock card once with that final
    number.
    """

    balances: dict[str, int] = {}

    for dataset in datasets:
        for card in dataset.mock_cards:
            if card.card_number in balances:
                raise RuntimeError(f"duplicate mock card seed: {card.card_number}")
            balances[card.card_number] = card.balance_cents

    for dataset in datasets:
        for reservation in dataset.reservations:
            for payment in reservation.payments:
                if payment.card_number not in balances:
                    raise RuntimeError(
                        f"seed dependency missing: card {payment.card_number!r} not found"
                    )
                if payment.action == PaymentAction.PRE_AUTH:
                    balances[payment.card_number] -= payment.amount_cents
                elif payment.action in {PaymentAction.RELEASE, PaymentAction.REFUND}:
                    balances[payment.card_number] += payment.amount_cents

    return balances


def _insert_bay(seed: ParkingBaySeed, stats: SeedStats) -> None:
    """Insert one bay record."""

    db.session.add(
        ParkingBay(
            code=seed.code,
            label=seed.label,
            device_id=seed.device_id,
            state=seed.state,
        )
    )
    stats.bays_created += 1


def _insert_user(seed: UserSeed, stats: SeedStats) -> User:
    """Insert one canonical demo user."""

    user = User(
        email=seed.email,
        name=seed.name,
        password_hash=hash_password(seed.password),
        role=seed.role,
    )
    db.session.add(user)
    db.session.flush()
    stats.users_created += 1
    return user


def _insert_plate(user: User, plate_seed: tuple[str, str], stats: SeedStats) -> None:
    """Insert one plate bound to a seeded user."""

    raw_plate, label = plate_seed
    db.session.add(
        LicencePlate(
            user_id=user.id,
            plate=plate_utils.normalise(raw_plate),
            label=label,
        )
    )
    stats.plates_created += 1


def _insert_mock_card(seed: MockCardSeed, stats: SeedStats, *, balance_cents: int) -> None:
    """Insert one mock-bank card with its final seeded balance."""

    db.session.add(
        MockCard(
            card_number=seed.card_number,
            cvv=seed.cvv,
            holder_name=seed.holder_name,
            expiry_month=seed.expiry_month,
            expiry_year=seed.expiry_year,
            balance_cents=balance_cents,
        )
    )
    stats.mock_cards_created += 1


def _resolve_time(now: datetime, offset_minutes: int | None) -> datetime | None:
    """Resolve an offset-based scenario timestamp from a shared seed ``now``."""

    if offset_minutes is None:
        return None
    return now + timedelta(minutes=offset_minutes)


def _require_user(email: str) -> User:
    """Load a previously seeded user or fail with a configuration error."""

    user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise RuntimeError(f"seed dependency missing: user {email!r} not found")
    return user


def _require_bay(code: str) -> ParkingBay:
    """Load a previously seeded bay or fail with a configuration error."""

    bay = db.session.execute(select(ParkingBay).where(ParkingBay.code == code)).scalar_one_or_none()
    if bay is None:
        raise RuntimeError(f"seed dependency missing: bay {code!r} not found")
    return bay


def _require_mock_card(number: str) -> MockCard:
    """Load a previously seeded card or fail with a configuration error."""

    card = db.session.execute(
        select(MockCard).where(MockCard.card_number == number)
    ).scalar_one_or_none()
    if card is None:
        raise RuntimeError(f"seed dependency missing: card {number!r} not found")
    return card


def _insert_reservation(seed: ReservationSeed, stats: SeedStats, *, now: datetime) -> Reservation:
    """Insert one relative-time reservation scenario."""

    user = _require_user(seed.user_email)
    bay = _require_bay(seed.bay_code)
    reservation = Reservation(
        id=UUID(seed.id),
        bay_id=bay.id,
        user_id=user.id,
        status=seed.status,
        expected_arrival_time=_resolve_time(now, seed.expected_arrival_offset_minutes),
        booked_at=_resolve_time(now, seed.booked_offset_minutes),
        check_in_grace_expires_at=_resolve_time(now, seed.check_in_grace_offset_minutes),
        checked_in_at=_resolve_time(now, seed.checked_in_offset_minutes),
        cancelled_at=_resolve_time(now, seed.cancelled_offset_minutes),
        completed_at=_resolve_time(now, seed.completed_offset_minutes),
        check_in_mechanism=seed.check_in_mechanism,
        check_in_recognised_plate=seed.check_in_recognised_plate,
    )
    db.session.add(reservation)
    db.session.flush()

    if seed.attach_to_bay:
        bay.current_reservation_id = reservation.id
    if seed.bay_state is not None:
        bay.state = seed.bay_state

    stats.reservations_created += 1
    return reservation


def _insert_payment(
    reservation: Reservation,
    seed: PaymentSeed,
    stats: SeedStats,
    *,
    now: datetime,
) -> None:
    """Insert one payment ledger row for a seeded reservation."""

    card = _require_mock_card(seed.card_number)

    if seed.action == PaymentAction.PRE_AUTH:
        parent_payment_id = None
    else:
        pre_auth = db.session.execute(
            select(Payment).where(
                Payment.reservation_id == reservation.id,
                Payment.action == PaymentAction.PRE_AUTH,
            )
        ).scalar_one_or_none()
        if pre_auth is None:
            raise RuntimeError(
                f"seed dependency missing: pre_auth for reservation {reservation.id} not found"
            )
        parent_payment_id = pre_auth.id

    source_event_id = UUID(seed.source_event_id) if seed.source_event_id is not None else None
    occurred_at = _resolve_time(now, seed.occurred_offset_minutes)
    if occurred_at is None:
        raise RuntimeError(f"seed payment {seed.idempotency_key!r} is missing occurred_at")

    db.session.add(
        Payment(
            reservation_id=reservation.id,
            user_id=reservation.user_id,
            mock_card_id=card.id,
            parent_payment_id=parent_payment_id,
            action=seed.action,
            penalty_kind=seed.penalty_kind,
            amount_cents=seed.amount_cents,
            status=seed.status,
            idempotency_key=seed.idempotency_key,
            source_event_id=source_event_id,
            occurred_at=occurred_at,
        )
    )
    db.session.flush()
    stats.payments_created += 1


def _insert_dataset(
    dataset: SeedDataset,
    stats: SeedStats,
    *,
    now: datetime,
    card_balances: dict[str, int],
) -> None:
    """Insert one dataset into the freshly reset database."""

    for bay in dataset.bays:
        _insert_bay(bay, stats)
    for user_seed in dataset.users:
        user = _insert_user(user_seed, stats)
        for plate_seed in user_seed.plates:
            _insert_plate(user, plate_seed, stats)
    for card in dataset.mock_cards:
        if card.card_number not in card_balances:
            raise RuntimeError(f"seed dependency missing: card {card.card_number!r} not found")
        _insert_mock_card(card, stats, balance_cents=card_balances[card.card_number])
    db.session.flush()

    for reservation_seed in dataset.reservations:
        reservation = _insert_reservation(reservation_seed, stats, now=now)
        for payment_seed in reservation_seed.payments:
            _insert_payment(reservation, payment_seed, stats, now=now)


def seed_datasets(
    datasets: list[SeedDataset], stats: SeedStats, *, now: datetime | None = None
) -> None:
    """Reset the database and insert the selected datasets."""

    now = now or utcnow()
    card_balances = _planned_card_balances(datasets)

    _reset_seed_tables()
    for dataset in datasets:
        _insert_dataset(dataset, stats, now=now, card_balances=card_balances)


def _print_datasets() -> None:
    """Print the dataset registry in a CLI-friendly format."""

    for name, dataset in sorted(BASE_DATASETS.items()):
        default_marker = " (default, base)" if name in DEFAULT_DATASET_NAMES else " (base)"
        print(f"{name}{default_marker}: {dataset.description}")
    for name, dataset in sorted(SCENARIO_DATASETS.items()):
        print(f"{name} (scenario): {dataset.description}")


def main() -> None:
    """CLI entrypoint used by ``make seed`` and manual development runs."""

    args = _parse_args()
    if args.list:
        _print_datasets()
        return

    datasets = _selected_datasets(args.datasets)
    stats = SeedStats()
    now = utcnow()

    app = create_app()
    with app.app_context():
        seed_datasets(datasets, stats, now=now)
        db.session.commit()

    names = ", ".join(dataset.name for dataset in datasets)
    print(f"seed: done ({names}) [{stats.summary()}]")


if __name__ == "__main__":
    main()
