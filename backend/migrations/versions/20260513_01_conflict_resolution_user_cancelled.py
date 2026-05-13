"""Add `user_cancelled` to the conflict_resolution enum.

Used by `reservation_service.cancel()` when the holder cancels while a strong
conflict is open on their bay (no-fault refund path) — distinct from
`admin_resolved` so the audit trail can tell facility action apart from a
victim's voluntary cancel.

Revision ID: 20260513_01
Revises: 20260421_01
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op

revision = "20260513_01"
down_revision = "20260421_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `ALTER TYPE ... ADD VALUE` is allowed inside a transaction since
    # PostgreSQL 12; the new value cannot be USED until after commit, which
    # is fine here — no migration data writes reference it.
    op.execute("ALTER TYPE conflict_resolution ADD VALUE IF NOT EXISTS 'user_cancelled'")


def downgrade() -> None:
    # PostgreSQL has no `DROP VALUE` for enum types. Reverting would require
    # rebuilding the enum (drop dependent column defaults, swap the type,
    # restore data), which isn't worth the complexity for a purely additive
    # change. Treat as a one-way migration.
    pass
