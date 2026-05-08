"""Runtime settings for the cloud backend.

All defaults match the prototype values documented in proposal §5.4 / §5.5
(grace periods, LPR confidence threshold, deposit + penalty amounts). They
are configurable per facility via environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields, replace


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
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://parkreserve:parkreserve@localhost:5432/parkreserve",
        )
    )
    port: int = field(default_factory=lambda: _env_int("PORT", 5000))
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

    # Reservation business rules (proposal §5.5) -----------------------
    booking_window_minutes: int = field(
        default_factory=lambda: _env_int("BOOKING_WINDOW_MINUTES", 60)
    )
    arrival_grace_minutes: int = field(default_factory=lambda: _env_int("ARRIVAL_GRACE_MINUTES", 5))
    check_in_grace_minutes: int = field(
        default_factory=lambda: _env_int("CHECK_IN_GRACE_MINUTES", 5)
    )
    late_cancel_cutoff_minutes: int = field(
        default_factory=lambda: _env_int("LATE_CANCEL_CUTOFF_MINUTES", 15)
    )
    plates_per_user_max: int = field(default_factory=lambda: _env_int("PLATES_PER_USER_MAX", 5))
    lpr_confidence_threshold: float = field(
        default_factory=lambda: _env_float("LPR_CONFIDENCE_THRESHOLD", 0.80)
    )

    # Mock-payment amounts in cents (proposal §5.5) --------------------
    deposit_cents: int = field(
        default_factory=lambda: _env_int("DEPOSIT_CENTS", 1000)  # $10
    )
    penalty_cents: int = field(
        default_factory=lambda: _env_int("PENALTY_CENTS", 500)  # $5 per breach kind
    )

    # Conflict-evidence retention (proposal §5.5) ----------------------
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
        default_factory=lambda: _env_int("RECONCILE_INTERVAL_SECONDS", 30)
    )
    purge_interval_hours: int = field(default_factory=lambda: _env_int("PURGE_INTERVAL_HOURS", 24))

    testing: bool = False

    @property
    def is_production(self) -> bool:
        return self.env == "production"


def load_settings(**overrides) -> Settings:
    base = Settings()
    if not overrides:
        return base
    known = {f.name for f in fields(base)}
    unknown = set(overrides) - known
    if unknown:
        raise TypeError(f"unknown settings overrides: {sorted(unknown)}")
    return replace(base, **overrides)
