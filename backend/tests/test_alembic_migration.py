"""Verify the Alembic migration runs cleanly upward and downward against a
fresh PostgreSQL — defends the "deploy script works on day 1" claim
for a fresh environment."""

from __future__ import annotations

import os

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _config(database_url: str) -> Config:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.set_main_option(
        "script_location",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "migrations")),
    )
    return cfg


@pytest.fixture()
def fresh_database(postgresql_proc, request):
    """A DB the alembic test owns end-to-end — independent from the `app`
    fixture which uses metadata.create_all."""
    db_name = f"parkreserve_alembic_{request.node.name[-20:].replace('[', '_').replace(']', '_')}"
    admin_url = (
        f"postgresql+psycopg://{postgresql_proc.user}:@"
        f"{postgresql_proc.host}:{postgresql_proc.port}/postgres"
    )
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        c.execute(text(f'CREATE DATABASE "{db_name}"'))
    db_url = (
        f"postgresql+psycopg://{postgresql_proc.user}:@"
        f"{postgresql_proc.host}:{postgresql_proc.port}/{db_name}"
    )
    yield db_url
    # Force-disconnect any lingering sessions (alembic's connection) before drop.
    with engine.connect() as c:
        c.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"
            )
        )
        c.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
    engine.dispose()


def test_alembic_upgrade_head_creates_all_expected_tables(fresh_database):
    cfg = _config(fresh_database)
    upgrade(cfg, "head")

    engine = create_engine(fresh_database)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    finally:
        engine.dispose()
    expected = {
        "users",
        "licence_plates",
        "parking_bays",
        "reservations",
        "mock_cards",
        "payments",
        "bay_events",
        "sensor_readings",
        "conflicts",
    }
    assert expected.issubset(tables), tables


def test_alembic_downgrade_then_upgrade_round_trips(fresh_database):
    cfg = _config(fresh_database)
    upgrade(cfg, "head")
    downgrade(cfg, "base")

    engine = create_engine(fresh_database)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    finally:
        engine.dispose()
    assert "parking_bays" not in tables
    assert "licence_plates" not in tables

    upgrade(cfg, "head")
    engine = create_engine(fresh_database)
    try:
        assert "parking_bays" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_alembic_seeds_three_demo_bays(fresh_database):
    cfg = _config(fresh_database)
    upgrade(cfg, "head")

    engine = create_engine(fresh_database)
    try:
        with engine.connect() as c:
            rows = c.execute(text("SELECT code FROM parking_bays ORDER BY code")).all()
    finally:
        engine.dispose()
    assert {r[0] for r in rows} == {"A1", "A2", "A3"}
