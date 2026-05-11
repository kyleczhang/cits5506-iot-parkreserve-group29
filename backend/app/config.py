"""Runtime settings for the cloud backend.

Defaults reflect the prototype parking flow: grace periods, LPR confidence
thresholds, and mock-payment amounts. They are configurable per facility via
environment variables.

:func:`load_settings` is the single entrypoint for building a :class:`Settings`
instance and the single place that consults ``backend/.env``. Construct
``Settings()`` directly only if you have a reason — ``load_settings()`` is the
documented path and what every entrypoint (``make dev``, scripts, Alembic,
tests) goes through.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields, replace
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Anchored to this file so loading is independent of cwd. Resolves to
# ``backend/.env`` — two levels up from ``app/config.py``.
_DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"


# Cache this helper so callers can safely invoke it whenever they need
# settings. We only want to read ``backend/.env`` once per process.
@lru_cache(maxsize=1)
def load_local_env() -> None:
    """Merge ``backend/.env`` into ``os.environ`` once for this process.

    Real environment variables exported by the shell, CI, or pytest fixtures
    remain authoritative because ``override=False``. A missing ``.env`` file is
    silently ignored, which is the right behaviour for containerised deploys
    that inject configuration directly.
    """
    load_dotenv(_DOTENV_PATH, override=False)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: os.getenv("FLASK_ENV", "development"))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret"))
    jwt_secret_key: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", "dev-jwt"))
    jwt_access_token_expires_hours: int = field(
        default_factory=lambda: _env_int("JWT_ACCESS_TOKEN_EXPIRES_HOURS", 72)
    )
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://parkreserve:parkreserve@localhost:5432/parkreserve",
        )
    )
    port: int = field(default_factory=lambda: _env_int("PORT", 8000))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
            if o.strip()
        )
    )

    # MQTT --------------------------------------------------------------
    mqtt_enabled: bool = field(default_factory=lambda: _env_bool("MQTT_ENABLED", True))
    mqtt_host: str = field(default_factory=lambda: os.getenv("MQTT_HOST", "localhost"))
    mqtt_port: int = field(default_factory=lambda: _env_int("MQTT_PORT", 1883))
    mqtt_tls: bool = field(default_factory=lambda: _env_bool("MQTT_TLS", False))
    mqtt_username: str | None = field(default_factory=lambda: os.getenv("MQTT_USERNAME") or None)
    mqtt_password: str | None = field(default_factory=lambda: os.getenv("MQTT_PASSWORD") or None)
    mqtt_client_id: str = field(
        default_factory=lambda: os.getenv("MQTT_CLIENT_ID", "parkreserve-backend")
    )
    mqtt_topic_prefix: str = field(default_factory=lambda: os.getenv("MQTT_TOPIC_PREFIX", "cloud"))

    # Reservation business rules ---------------------------------------
    booking_window_minutes: int = field(
        default_factory=lambda: _env_int(
            "BOOKING_WINDOW_MINUTES", 60
        )  # Max lead time for creating a reservation.
    )
    arrival_grace_minutes: int = field(
        default_factory=lambda: _env_int(
            "ARRIVAL_GRACE_MINUTES", 5
        )  # No-show grace after expected arrival.
    )
    check_in_grace_minutes: int = field(
        default_factory=lambda: _env_int(
            "CHECK_IN_GRACE_MINUTES", 5
        )  # Time allowed to complete manual check-in.
    )
    late_cancel_cutoff_minutes: int = field(
        default_factory=lambda: _env_int(
            "LATE_CANCEL_CUTOFF_MINUTES", 15
        )  # Cancels inside this window count as late.
    )
    plates_per_user_max: int = field(
        default_factory=lambda: _env_int(
            "PLATES_PER_USER_MAX", 5
        )  # Max licence plates one account can bind.
    )
    lpr_confidence_threshold: float = field(
        default_factory=lambda: _env_float(
            "LPR_CONFIDENCE_THRESHOLD", 0.80
        )  # Reserved threshold for accepting LPR matches.
    )

    # Mock-payment amounts in cents ------------------------------------
    deposit_cents: int = field(
        default_factory=lambda: _env_int("DEPOSIT_CENTS", 1000)  # $10
    )
    penalty_cents: int = field(
        default_factory=lambda: _env_int("PENALTY_CENTS", 500)  # $5 per breach kind
    )

    # Conflict-evidence retention --------------------------------------
    evidence_retention_days: int = field(
        default_factory=lambda: _env_int("EVIDENCE_RETENTION_DAYS", 30)
    )
    evidence_storage_path: str = field(
        default_factory=lambda: os.getenv("EVIDENCE_STORAGE_PATH", "/var/lib/parkreserve/evidence")
    )
    evidence_upload_token: str | None = field(
        default_factory=lambda: os.getenv("EVIDENCE_UPLOAD_TOKEN") or None
    )

    # Background jobs --------------------------------------------------
    reconcile_interval_seconds: int = field(
        default_factory=lambda: _env_int(
            "RECONCILE_INTERVAL_SECONDS", 30
        )  # How often the safety-net sweeper runs to synthesise missed no_show / conflict_weak events.
    )
    purge_interval_hours: int = field(
        default_factory=lambda: _env_int(
            "PURGE_INTERVAL_HOURS", 24
        )  # How often to purge expired strong-conflict evidence images from storage.
    )

    testing: bool = False

    @property
    def is_production(self) -> bool:
        return self.env == "production"


def load_settings(**overrides) -> Settings:
    """Build settings from environment variables, then apply validated overrides.

    ``backend/.env`` is merged into ``os.environ`` first so documented
    entrypoints such as ``make dev``, CLI scripts, and tests see the same
    configuration defaults unless the surrounding process has already exported
    a real environment variable.

    Unknown override keys raise ``TypeError`` so tests and one-off scripts do
    not silently pass misspelled setting names.
    """
    load_local_env()
    base = Settings()
    if not overrides:
        return base
    known = {f.name for f in fields(base)}
    unknown = set(overrides) - known
    if unknown:
        raise TypeError(f"unknown settings overrides: {sorted(unknown)}")
    return replace(base, **overrides)
