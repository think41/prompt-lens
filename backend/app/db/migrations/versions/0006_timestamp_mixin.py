"""TimestampMixin: standardise created_at/updated_at on all tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-09

Changes:
- developers: rename first_seen_at → created_at, last_seen_at → updated_at
- teams: add updated_at (backfill from created_at)
- projects: add updated_at (backfill from created_at)
- sessions: add created_at (backfill from started_at), add updated_at (backfill from started_at)
- turns: add updated_at (backfill from created_at)
- tool_events: add updated_at (backfill from created_at)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── developers ──────────────────────────────────────────────────────────
    op.alter_column("developers", "first_seen_at", new_column_name="created_at")
    op.alter_column("developers", "last_seen_at", new_column_name="updated_at")

    # ── teams ────────────────────────────────────────────────────────────────
    op.add_column(
        "teams",
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute("UPDATE teams SET updated_at = created_at")
    op.alter_column("teams", "updated_at", nullable=False)

    # ── projects ─────────────────────────────────────────────────────────────
    op.add_column(
        "projects",
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute("UPDATE projects SET updated_at = created_at")
    op.alter_column("projects", "updated_at", nullable=False)

    # ── sessions ─────────────────────────────────────────────────────────────
    op.add_column(
        "sessions",
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute("UPDATE sessions SET created_at = started_at")
    op.alter_column("sessions", "created_at", nullable=False)

    op.add_column(
        "sessions",
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute("UPDATE sessions SET updated_at = started_at")
    op.alter_column("sessions", "updated_at", nullable=False)

    # ── turns ────────────────────────────────────────────────────────────────
    op.add_column(
        "turns",
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute("UPDATE turns SET updated_at = created_at")
    op.alter_column("turns", "updated_at", nullable=False)

    # ── tool_events ──────────────────────────────────────────────────────────
    op.add_column(
        "tool_events",
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute("UPDATE tool_events SET updated_at = created_at")
    op.alter_column("tool_events", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("tool_events", "updated_at")
    op.drop_column("turns", "updated_at")
    op.drop_column("sessions", "updated_at")
    op.drop_column("sessions", "created_at")
    op.drop_column("projects", "updated_at")
    op.drop_column("teams", "updated_at")
    op.alter_column("developers", "updated_at", new_column_name="last_seen_at")
    op.alter_column("developers", "created_at", new_column_name="first_seen_at")
