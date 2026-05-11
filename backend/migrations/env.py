"""Alembic environment for the ParkReserve backend.

This module is Alembic's bootstrap entrypoint for both migration execution
and autogeneration. It wires the migration context to the application's
SQLAlchemy metadata without constructing the full Flask runtime, so schema
changes can be applied independently of HTTP, MQTT, or scheduler startup.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Make the `app` package importable when Alembic is invoked from `backend/`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_local_env
from app.extensions import Base, db
from app import models

load_local_env()

# Alembic's parsed `alembic.ini` config object for this migration run.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    """Resolve the database URL for the current migration invocation.

    Resolution order is:
    1. `DATABASE_URL` from the environment
    2. `sqlalchemy.url` from `alembic.ini`
    3. a local development fallback
    """
    return (
        os.getenv("DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
        or "postgresql+psycopg://parkreserve:parkreserve@localhost:5432/parkreserve"
    )


# Metadata used by Alembic autogenerate to diff models against the database.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode.

    Offline mode does not open a live database connection. Alembic instead
    configures the context with a URL and emits SQL directly from migration
    operations and metadata comparisons.
    """
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection.

    Online mode creates an engine, opens a connection, binds that connection
    into Alembic's context, and executes migration steps inside a transaction.
    """
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
