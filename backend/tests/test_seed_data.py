from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extensions import db
from app.models import MockCard, Payment, Reservation, User, UserRole
from app.utils.security import hash_password
from scripts.seed import SeedStats, _selected_datasets, seed_datasets


def test_selected_datasets_defaults_to_demo():
    datasets = _selected_datasets(None)

    assert [dataset.name for dataset in datasets] == ["demo"]


def test_selected_datasets_rejects_unknown_name():
    with pytest.raises(SystemExit, match="unknown dataset"):
        _selected_datasets(["missing"])


def test_selected_datasets_include_demo_for_extensions():
    datasets = _selected_datasets(["integration_ready", "payments_history"])

    assert [dataset.name for dataset in datasets] == [
        "demo",
        "integration_ready",
        "payments_history",
    ]


def test_seed_datasets_resets_and_rebuilds_demo_state(app):
    datasets = _selected_datasets(["demo"])

    with app.app_context():
        first = SeedStats()
        seed_datasets(datasets, first)
        db.session.commit()

        db.session.add(
            User(
                email="leftover@parkreserve.local",
                name="Leftover User",
                password_hash=hash_password("leftoverParkreserve29!"),
                role=UserRole.USER,
            )
        )
        db.session.commit()

        assert first.bays_created == 3
        assert first.users_created == 5
        assert first.plates_created == 5
        assert first.mock_cards_created == 10
        assert first.reservations_created == 0
        assert first.payments_created == 0

        second = SeedStats()
        seed_datasets(datasets, second)
        db.session.commit()

        users = list(db.session.execute(select(User)).scalars())

        assert second.bays_created == 3
        assert second.users_created == 5
        assert second.plates_created == 5
        assert second.mock_cards_created == 10
        assert second.reservations_created == 0
        assert second.payments_created == 0
        assert len(users) == 5
        assert {user.email for user in users} == {
            "nyx@parkreserve.local",
            "riya@parkreserve.local",
            "yuan@parkreserve.local",
            "cheng@parkreserve.local",
            "admin@parkreserve.local",
        }


def test_seed_datasets_seed_reservations_payments_and_balances(app):
    datasets = _selected_datasets(
        [
            "integration_ready",
            "integration_conflict",
            "integration_checked_in",
            "payments_history",
        ]
    )

    with app.app_context():
        stats = SeedStats()
        seed_datasets(datasets, stats)

        reservations = list(db.session.execute(select(Reservation)).scalars())
        payments = list(db.session.execute(select(Payment)).scalars())
        cards = {card.card_number: card for card in db.session.execute(select(MockCard)).scalars()}

        assert stats.reservations_created == 7
        assert stats.payments_created == 13
        assert len(reservations) == 7
        assert len(payments) == 13
        assert cards["4111111111111001"].balance_cents == 140_00
        assert cards["4222222222222001"].balance_cents == 110_00
        assert cards["4444444444444001"].balance_cents == 170_00
        assert cards["4444444444444002"].balance_cents == 55_00
        assert cards["4555555555555001"].balance_cents == 495_00
