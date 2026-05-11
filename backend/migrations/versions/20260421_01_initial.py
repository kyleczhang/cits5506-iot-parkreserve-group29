"""Initial schema for the LPR-based parking flow.

Revision ID: 20260421_01
Revises:
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260421_01"
down_revision = None
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

USER_ROLE = postgresql.ENUM("user", "admin", name="user_role", create_type=False)

BAY_STATE = postgresql.ENUM(
    "available",
    "reserved",
    "occupied",
    "pending_check_in",
    "reserved_checked_in",
    "conflict",
    "offline",
    name="bay_state",
    create_type=False,
)

RESERVATION_STATUS = postgresql.ENUM(
    "active",
    "pending_check_in",
    "checked_in",
    "completed",
    "cancelled",
    "cancelled_late",
    "expired_no_show",
    "in_conflict",
    name="reservation_status",
    create_type=False,
)

CHECK_IN_MECHANISM = postgresql.ENUM(
    "auto_lpr",
    "qr",
    "manual",
    name="check_in_mechanism",
    create_type=False,
)

PENALTY_KIND = postgresql.ENUM(
    "late_cancel",
    "no_show",
    "weak_conflict",
    name="penalty_kind",
    create_type=False,
)

PAYMENT_ACTION = postgresql.ENUM(
    "pre_auth",
    "release",
    "refund",
    "penalty_capture",
    name="payment_action",
    create_type=False,
)

PAYMENT_STATUS = postgresql.ENUM(
    "succeeded",
    "failed",
    "voided",
    name="payment_status",
    create_type=False,
)

BAY_EVENT_KIND = postgresql.ENUM(
    "state_changed",
    "sensor_online",
    "sensor_offline",
    "pending_check_in",
    "auto_check_in",
    "check_in_confirmed",
    "conflict_strong",
    "conflict_weak",
    "conflict_resolved",
    "no_show",
    "reservation_created",
    "reservation_cancelled",
    "reservation_completed",
    "plates_updated",
    name="bay_event_kind",
    create_type=False,
)

CONFLICT_KIND = postgresql.ENUM(
    "strong",
    "weak",
    name="conflict_kind",
    create_type=False,
)

CONFLICT_RESOLUTION = postgresql.ENUM(
    "user_arrived_and_checked_in",
    "vehicle_left",
    "admin_resolved",
    name="conflict_resolution",
    create_type=False,
)

ALL_ENUMS = (
    USER_ROLE,
    BAY_STATE,
    RESERVATION_STATUS,
    CHECK_IN_MECHANISM,
    PENALTY_KIND,
    PAYMENT_ACTION,
    PAYMENT_STATUS,
    BAY_EVENT_KIND,
    CONFLICT_KIND,
    CONFLICT_RESOLUTION,
)


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

LICENCE_PLATES_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION licence_plates_max_per_user()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT COUNT(*) FROM licence_plates WHERE user_id = NEW.user_id) >= 5 THEN
        RAISE EXCEPTION 'plate_limit_exceeded'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
"""

LICENCE_PLATES_TRIGGER = """
CREATE TRIGGER licence_plates_max_per_user_tg
BEFORE INSERT ON licence_plates
FOR EACH ROW EXECUTE FUNCTION licence_plates_max_per_user();
"""


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))

    for enum in ALL_ENUMS:
        enum.create(bind, checkfirst=True)

    # users -----------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", USER_ROLE, nullable=False, server_default=sa.text("'user'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("email", name="users_email_unique"),
    )
    op.create_index(
        "users_role_idx",
        "users",
        ["role"],
        postgresql_where=sa.text("role = 'admin'"),
    )

    # licence_plates --------------------------------------------------------
    op.create_table(
        "licence_plates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plate", sa.String(16), nullable=False),
        sa.Column("label", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "plate", name="licence_plates_user_plate_unique"),
        sa.CheckConstraint("plate ~ '^[A-Z0-9]{1,10}$'", name="licence_plates_format"),
    )
    op.create_index("licence_plates_user_idx", "licence_plates", ["user_id"])
    op.create_index("licence_plates_plate_idx", "licence_plates", ["plate"])
    bind.execute(sa.text(LICENCE_PLATES_TRIGGER_FN))
    bind.execute(sa.text(LICENCE_PLATES_TRIGGER))

    # parking_bays ----------------------------------------------------------
    op.create_table(
        "parking_bays",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("device_id", sa.String(64), nullable=True),
        sa.Column("state", BAY_STATE, nullable=False, server_default=sa.text("'offline'")),
        sa.Column("last_distance_cm", sa.Numeric(6, 2), nullable=True),
        sa.Column("sensor_last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_reservation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("code", name="parking_bays_code_unique"),
        sa.UniqueConstraint("device_id", name="parking_bays_device_unique"),
    )
    op.create_index("parking_bays_state_idx", "parking_bays", ["state"])

    # reservations ----------------------------------------------------------
    op.create_table(
        "reservations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("bay_id", sa.Integer(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", RESERVATION_STATUS, nullable=False, server_default=sa.text("'active'")),
        sa.Column("expected_arrival_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "booked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("check_in_grace_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_in_mechanism", CHECK_IN_MECHANISM, nullable=True),
        sa.Column("check_in_recognised_plate", sa.String(16), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["bay_id"], ["parking_bays.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "expected_arrival_time > booked_at "
            "AND expected_arrival_time <= booked_at + INTERVAL '1 hour'",
            name="reservations_booking_window",
        ),
        sa.CheckConstraint(
            "(status = 'checked_in' AND checked_in_at IS NOT NULL "
            "                       AND check_in_mechanism IS NOT NULL) "
            "OR status <> 'checked_in'",
            name="reservations_checked_in_has_ts",
        ),
        sa.CheckConstraint(
            "(status IN ('cancelled', 'cancelled_late') AND cancelled_at IS NOT NULL) "
            "OR status NOT IN ('cancelled', 'cancelled_late')",
            name="reservations_cancelled_has_ts",
        ),
        sa.CheckConstraint(
            "(check_in_mechanism = 'auto_lpr' AND check_in_recognised_plate IS NOT NULL) "
            "OR (check_in_mechanism IN ('qr', 'manual') AND check_in_recognised_plate IS NULL) "
            "OR (check_in_mechanism IS NULL AND check_in_recognised_plate IS NULL)",
            name="reservations_check_in_plate_matches_mechanism",
        ),
    )
    op.create_index(
        "reservations_one_open_per_bay",
        "reservations",
        ["bay_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'pending_check_in', 'checked_in')"),
    )
    op.create_index("reservations_user_idx", "reservations", ["user_id", "booked_at"])
    op.create_index(
        "reservations_arrival_idx",
        "reservations",
        ["expected_arrival_time"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "reservations_check_in_grace_idx",
        "reservations",
        ["check_in_grace_expires_at"],
        postgresql_where=sa.text("status = 'pending_check_in'"),
    )

    # parking_bays.current_reservation_id FK (deferrable, circular)
    op.create_foreign_key(
        "parking_bays_current_reservation_fk",
        "parking_bays",
        "reservations",
        ["current_reservation_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )

    # mock_cards (mock-bank simulator) -------------------------------------
    op.create_table(
        "mock_cards",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("card_number", sa.String(19), nullable=False),
        sa.Column("cvv", sa.String(4), nullable=False),
        sa.Column("holder_name", sa.String(120), nullable=False),
        sa.Column("expiry_month", sa.Integer(), nullable=False),
        sa.Column("expiry_year", sa.Integer(), nullable=False),
        sa.Column("balance_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("card_number", name="mock_cards_number_unique"),
        sa.CheckConstraint("card_number ~ '^[0-9]{13,19}$'", name="mock_cards_number_format"),
        sa.CheckConstraint("cvv ~ '^[0-9]{3,4}$'", name="mock_cards_cvv_format"),
        sa.CheckConstraint("expiry_month BETWEEN 1 AND 12", name="mock_cards_expiry_month"),
        sa.CheckConstraint("expiry_year BETWEEN 2024 AND 2099", name="mock_cards_expiry_year"),
        sa.CheckConstraint("balance_cents >= 0", name="mock_cards_balance_nonneg"),
    )
    op.create_index("mock_cards_number_idx", "mock_cards", ["card_number"])

    # payments (transactions ledger) ---------------------------------------
    op.create_table(
        "payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mock_card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", PAYMENT_ACTION, nullable=False),
        sa.Column("penalty_kind", PENALTY_KIND, nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("status", PAYMENT_STATUS, nullable=False, server_default=sa.text("'succeeded'")),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mock_card_id"], ["mock_cards.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("idempotency_key", name="payments_idempotency_key_unique"),
        sa.CheckConstraint("amount_cents >= 0", name="payments_amount_nonneg"),
        sa.CheckConstraint(
            "(action = 'pre_auth' AND parent_payment_id IS NULL)"
            " OR (action <> 'pre_auth' AND parent_payment_id IS NOT NULL)",
            name="payments_parent_required",
        ),
        sa.CheckConstraint(
            "(action = 'penalty_capture' AND penalty_kind IS NOT NULL)"
            " OR (action <> 'penalty_capture' AND penalty_kind IS NULL)",
            name="payments_penalty_kind_only_for_penalty",
        ),
    )
    op.create_index("payments_reservation_idx", "payments", ["reservation_id", "occurred_at"])
    op.create_index(
        "payments_user_time_idx",
        "payments",
        ["user_id", sa.text("occurred_at DESC")],
    )
    op.create_index("payments_card_idx", "payments", ["mock_card_id"])
    op.create_index(
        "payments_one_preauth_per_reservation",
        "payments",
        ["reservation_id"],
        unique=True,
        postgresql_where=sa.text("action = 'pre_auth'"),
    )
    op.create_index(
        "payments_source_event_unique",
        "payments",
        ["source_event_id"],
        unique=True,
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
    )

    # sensor_readings -------------------------------------------------------
    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("bay_id", sa.Integer(), nullable=False),
        sa.Column("distance_cm", sa.Numeric(6, 2), nullable=False),
        sa.Column("occupied", sa.Boolean(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["bay_id"], ["parking_bays.id"], ondelete="CASCADE"),
    )
    op.create_index("sensor_readings_bay_time_idx", "sensor_readings", ["bay_id", "recorded_at"])

    # bay_events ------------------------------------------------------------
    op.create_table(
        "bay_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("bay_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", BAY_EVENT_KIND, nullable=False),
        sa.Column("from_state", BAY_STATE, nullable=True),
        sa.Column("to_state", BAY_STATE, nullable=True),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["bay_id"], ["parking_bays.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("source_event_id", name="bay_events_source_event_unique"),
    )
    op.create_index("bay_events_bay_time_idx", "bay_events", ["bay_id", "created_at"])
    op.create_index("bay_events_kind_idx", "bay_events", ["kind"])

    # conflicts -------------------------------------------------------------
    op.create_table(
        "conflicts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("bay_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", CONFLICT_KIND, nullable=False),
        sa.Column("recognised_plate", sa.String(16), nullable=True),
        sa.Column("lpr_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("evidence_image_url", sa.Text(), nullable=True),
        sa.Column("image_purge_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", CONFLICT_RESOLUTION, nullable=True),
        sa.ForeignKeyConstraint(["bay_id"], ["parking_bays.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("source_event_id", name="conflicts_source_event_unique"),
        sa.CheckConstraint(
            "(resolved_at IS NULL AND resolution IS NULL) OR "
            "(resolved_at IS NOT NULL AND resolution IS NOT NULL)",
            name="conflicts_resolution_consistent",
        ),
        sa.CheckConstraint(
            "(kind = 'strong' AND recognised_plate IS NOT NULL) OR "
            "(kind = 'weak'   AND recognised_plate IS NULL "
            "                  AND evidence_image_url IS NULL)",
            name="conflicts_evidence_matches_kind",
        ),
        sa.CheckConstraint(
            "kind <> 'strong' OR resolution IS DISTINCT FROM 'user_arrived_and_checked_in'",
            name="conflicts_strong_resolution_excludes_user_check_in",
        ),
    )
    op.create_index(
        "conflicts_one_open_per_bay",
        "conflicts",
        ["bay_id"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    op.create_index(
        "conflicts_image_purge_idx",
        "conflicts",
        ["image_purge_at"],
        postgresql_where=sa.text("evidence_image_url IS NOT NULL AND image_purge_at IS NOT NULL"),
    )

    # Seed 3 demo bays so dashboard has something from boot.
    op.execute(
        "INSERT INTO parking_bays (code, label, device_id, state) VALUES "
        "('A1', 'Bay A1', 'esp32-a1', 'offline'),"
        "('A2', 'Bay A2', 'esp32-a2', 'offline'),"
        "('A3', 'Bay A3', 'esp32-a3', 'offline')"
    )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    op.drop_constraint(
        "parking_bays_current_reservation_fk",
        "parking_bays",
        type_="foreignkey",
    )
    op.drop_table("conflicts")
    op.drop_table("bay_events")
    op.drop_table("sensor_readings")
    op.drop_table("payments")
    op.drop_table("mock_cards")
    op.drop_table("reservations")
    op.drop_table("parking_bays")
    op.execute("DROP TRIGGER IF EXISTS licence_plates_max_per_user_tg ON licence_plates")
    op.execute("DROP FUNCTION IF EXISTS licence_plates_max_per_user()")
    op.drop_table("licence_plates")
    op.drop_table("users")

    bind = op.get_bind()
    for enum in reversed(ALL_ENUMS):
        enum.drop(bind, checkfirst=True)
