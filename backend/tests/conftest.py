"""Shared pytest fixtures for app setup, database state, and authenticated users."""

from __future__ import annotations

import os
import tempfile

import pytest
from pytest_postgresql import factories
from sqlalchemy import text

from app import create_app
from app.config import load_settings
from app.extensions import Base, db
from app.models import (
    BayState,
    LicencePlate,
    MockCard,
    ParkingBay,
    User,
    UserRole,
)
from app.schemas.payment import CardDetails
from app.utils.security import hash_password

# Spin up a real PostgreSQL cluster once per test session.
postgresql_proc = factories.postgresql_proc(
    port=None,
    postgres_options="-c fsync=off -c synchronous_commit=off -c full_page_writes=off",
)
postgresql = factories.postgresql("postgresql_proc", dbname="parkreserve_test")


def _database_url(proc) -> str:
    return f"postgresql+psycopg://{proc.user}:@{proc.host}:{proc.port}/parkreserve_test"


@pytest.fixture(scope="session")
def _evidence_dir():
    with tempfile.TemporaryDirectory(prefix="parkreserve-evidence-") as d:
        yield d


@pytest.fixture()
def _settings(postgresql_proc, _evidence_dir):
    return load_settings(
        database_url=_database_url(postgresql_proc),
        mqtt_enabled=False,
        testing=True,
        secret_key="test-secret-key-of-sufficient-length-for-jwt",
        jwt_secret_key="test-jwt-key-of-sufficient-length-for-tests-please",
        evidence_storage_path=_evidence_dir,
        evidence_upload_token="test-evidence-token",
    )


@pytest.fixture()
def app(_settings, postgresql):
    """A fresh Flask app bound to the per-test PostgreSQL database."""
    os.environ["DATABASE_URL"] = _settings.database_url
    flask_app = create_app(settings=_settings)

    with flask_app.app_context():
        _enable_extensions()
        Base.metadata.create_all(db.engine)

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        Base.metadata.drop_all(db.engine)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture()
def bays(session) -> list[ParkingBay]:
    existing = list(session.execute(db.select(ParkingBay)).scalars())
    if existing:
        return existing
    rows = [
        ParkingBay(code="A1", label="Bay A1", device_id="esp32-a1", state=BayState.AVAILABLE),
        ParkingBay(code="A2", label="Bay A2", device_id="esp32-a2", state=BayState.AVAILABLE),
        ParkingBay(code="A3", label="Bay A3", device_id="esp32-a3", state=BayState.AVAILABLE),
    ]
    session.add_all(rows)
    session.commit()
    return rows


@pytest.fixture()
def user(session) -> User:
    u = User(
        email="driver@test.local",
        name="Test Driver",
        password_hash=hash_password("password1!"),
        role=UserRole.USER,
    )
    session.add(u)
    session.commit()
    return u


@pytest.fixture()
def user_with_plates(session, user) -> User:
    """A regular user with two bound plates — the default for reservation tests."""
    session.add_all(
        [
            LicencePlate(user_id=user.id, plate="ABC123", label="My car"),
            LicencePlate(user_id=user.id, plate="XYZ789", label="Wife's car"),
        ]
    )
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture()
def mock_cards(session) -> list[MockCard]:
    """Three demo mock cards: a funded one, an empty one, and an expired one."""
    existing = list(session.execute(db.select(MockCard)).scalars())
    if existing:
        return existing
    rows = [
        MockCard(
            card_number="4111111111111111",
            cvv="123",
            holder_name="Test Driver",
            expiry_month=12,
            expiry_year=2030,
            balance_cents=10_000,
        ),
        MockCard(
            card_number="4222222222222222",
            cvv="234",
            holder_name="Test Driver",
            expiry_month=12,
            expiry_year=2030,
            balance_cents=0,
        ),
        MockCard(
            card_number="4333333333333333",
            cvv="345",
            holder_name="Test Driver",
            expiry_month=1,
            expiry_year=2024,
            balance_cents=10_000,
        ),
    ]
    session.add_all(rows)
    session.commit()
    return rows


def card_body(card: CardDetails) -> dict:
    """Helper: serialise a :class:`CardDetails` for inclusion in a booking POST body."""
    return {
        "number": card.number,
        "cvv": card.cvv,
        "expiry_month": card.expiry_month,
        "expiry_year": card.expiry_year,
        "holder_name": card.holder_name,
    }


@pytest.fixture()
def card(mock_cards) -> CardDetails:
    """The default funded card matching the first ``mock_cards`` row."""
    c = mock_cards[0]
    return CardDetails(
        number=c.card_number,
        cvv=c.cvv,
        expiry_month=c.expiry_month,
        expiry_year=c.expiry_year,
        holder_name=c.holder_name,
    )


@pytest.fixture()
def admin(session) -> User:
    u = User(
        email="admin@test.local",
        name="Test Admin",
        password_hash=hash_password("password1!"),
        role=UserRole.ADMIN,
    )
    session.add(u)
    session.commit()
    return u


@pytest.fixture()
def auth_headers(app, user_with_plates) -> dict[str, str]:
    """Headers for the regular `user_with_plates` driver."""
    return _bearer(app, user_with_plates)


@pytest.fixture()
def admin_headers(app, admin) -> dict[str, str]:
    return _bearer(app, admin)


def _bearer(app, user: User) -> dict[str, str]:
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(
            identity=str(user.id), additional_claims={"role": user.role.value}
        )
    return {"Authorization": f"Bearer {token}"}


def _enable_extensions() -> None:
    with db.engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
