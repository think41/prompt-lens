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
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    bind = op.get_bind()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _add_col_if_missing(table: str, col: str, backfill_sql: str) -> None:
    if col not in _columns(table):
        op.add_column(table, sa.Column(col, TIMESTAMP(timezone=True), nullable=True))
        op.execute(backfill_sql)
        op.alter_column(table, col, nullable=False)


def upgrade() -> None:
    # ── developers ──────────────────────────────────────────────────────────
    cols = _columns("developers")
    if "first_seen_at" in cols and "created_at" not in cols:
        op.alter_column("developers", "first_seen_at", new_column_name="created_at")
    if "last_seen_at" in cols and "updated_at" not in cols:
        op.alter_column("developers", "last_seen_at", new_column_name="updated_at")

    # ── teams ────────────────────────────────────────────────────────────────
    _add_col_if_missing("teams", "updated_at", "UPDATE teams SET updated_at = created_at")

    # ── projects ─────────────────────────────────────────────────────────────
    _add_col_if_missing("projects", "updated_at", "UPDATE projects SET updated_at = created_at")

    # ── sessions ─────────────────────────────────────────────────────────────
    _add_col_if_missing("sessions", "created_at", "UPDATE sessions SET created_at = started_at")
    _add_col_if_missing("sessions", "updated_at", "UPDATE sessions SET updated_at = started_at")

    # ── turns ────────────────────────────────────────────────────────────────
    _add_col_if_missing("turns", "updated_at", "UPDATE turns SET updated_at = created_at")

    # ── tool_events ──────────────────────────────────────────────────────────
    _add_col_if_missing("tool_events", "updated_at", "UPDATE tool_events SET updated_at = created_at")


def downgrade() -> None:
    op.drop_column("tool_events", "updated_at")
    op.drop_column("turns", "updated_at")
    op.drop_column("sessions", "updated_at")
    op.drop_column("sessions", "created_at")
    op.drop_column("projects", "updated_at")
    op.drop_column("teams", "updated_at")
    op.alter_column("developers", "updated_at", new_column_name="last_seen_at")
    op.alter_column("developers", "created_at", new_column_name="first_seen_at")
