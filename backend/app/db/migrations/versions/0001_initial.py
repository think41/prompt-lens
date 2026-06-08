"""Initial schema: sessions, turns, tool_events

Revision ID: 0001
Revises:
Create Date: 2026-06-05
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False, unique=True),
        sa.Column("developer_id", sa.String(64), nullable=False),
        sa.Column("team_id", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("turns", sa.Integer(), server_default="0"),
        sa.Column("cwd_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_sessions_session_id", "sessions", ["session_id"])
    op.create_index("ix_sessions_developer_id", "sessions", ["developer_id"])

    op.create_table(
        "turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(128), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("developer_id", sa.String(64), nullable=False),
        sa.Column("team_id", sa.String(64), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("prompt_chars", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("flags", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_turns_session_id", "turns", ["session_id"])
    op.create_index("ix_turns_developer_id", "turns", ["developer_id"])

    op.create_table(
        "tool_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(128), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("developer_id", sa.String(64), nullable=False),
        sa.Column("team_id", sa.String(64), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("accept_streak", sa.Integer(), server_default="0"),
        sa.Column("total_accepts", sa.Integer(), server_default="0"),
        sa.Column("total_rejects", sa.Integer(), server_default="0"),
        sa.Column("sensitive_path", sa.Boolean(), server_default="false"),
        sa.Column("file_path_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tool_events_session_id", "tool_events", ["session_id"])
    op.create_index("ix_tool_events_developer_id", "tool_events", ["developer_id"])


def downgrade() -> None:
    op.drop_table("tool_events")
    op.drop_table("turns")
    op.drop_table("sessions")
