"""Normalize schema: developers, teams, projects tables; remove duplicated columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-09

Changes:
- NEW tables: developers, teams, projects
- sessions: add project_id FK, updated_at; rename turns→turn_count;
  drop developer_name, developer_email, project_url, project_name
- turns: drop developer_id, team_id (derive via session JOIN)
- tool_events: drop developer_id, team_id, total_accepts, total_rejects
- Add CHECK constraints, FKs, composite indexes
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. New lookup tables ─────────────────────────────────────────────────

    op.create_table(
        "developers",
        sa.Column("developer_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), nullable=True),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "teams",
        sa.Column("team_id", sa.String(64), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.String(64), sa.ForeignKey("teams.team_id"), nullable=False),
        sa.Column("project_url", sa.Text, nullable=True),
        sa.Column("project_name", sa.String(256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("team_id", "project_name", name="uq_projects_team_name"),
    )

    # ── 2. Backfill lookup tables from existing sessions ─────────────────────

    op.execute("""
        INSERT INTO developers (developer_id, name, email, first_seen_at, last_seen_at)
        SELECT
            developer_id,
            MAX(developer_name)  AS name,
            MAX(developer_email) AS email,
            MIN(started_at)      AS first_seen_at,
            MAX(started_at)      AS last_seen_at
        FROM sessions
        WHERE developer_id IS NOT NULL
        GROUP BY developer_id
        ON CONFLICT DO NOTHING
    """)

    op.execute("""
        INSERT INTO teams (team_id)
        SELECT DISTINCT team_id FROM sessions WHERE team_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)

    op.execute("""
        INSERT INTO projects (team_id, project_url, project_name)
        SELECT DISTINCT ON (team_id, project_name)
            team_id,
            project_url,
            project_name
        FROM sessions
        WHERE team_id IS NOT NULL AND project_name IS NOT NULL
        ORDER BY team_id, project_name, started_at DESC
        ON CONFLICT (team_id, project_name) DO NOTHING
    """)

    # ── 3. sessions: add project_id FK + updated_at ──────────────────────────

    op.add_column("sessions", sa.Column("project_id", sa.Integer, nullable=True))
    op.execute("""
        UPDATE sessions s
        SET project_id = p.id
        FROM projects p
        WHERE p.team_id = s.team_id
          AND p.project_name = s.project_name
    """)
    op.create_foreign_key(
        "fk_sessions_project_id", "sessions", "projects", ["project_id"], ["id"]
    )

    op.add_column(
        "sessions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("NOW()"),
        ),
    )
    op.execute("UPDATE sessions SET updated_at = COALESCE(ended_at, started_at, NOW())")

    # ── 4. sessions: rename turns → turn_count, add FKs ─────────────────────

    op.alter_column("sessions", "turns", new_column_name="turn_count")

    op.create_foreign_key(
        "fk_sessions_developer_id", "sessions", "developers", ["developer_id"], ["developer_id"]
    )
    op.create_foreign_key(
        "fk_sessions_team_id", "sessions", "teams", ["team_id"], ["team_id"]
    )

    # ── 5. sessions: drop denormalised columns ───────────────────────────────

    op.drop_column("sessions", "developer_name")
    op.drop_column("sessions", "developer_email")
    op.drop_column("sessions", "project_url")
    op.drop_column("sessions", "project_name")

    # ── 6. turns: drop denormalised developer_id / team_id ───────────────────

    op.drop_column("turns", "developer_id")
    op.drop_column("turns", "team_id")

    # ── 7. tool_events: drop denormalised columns ────────────────────────────

    op.drop_column("tool_events", "developer_id")
    op.drop_column("tool_events", "team_id")
    op.drop_column("tool_events", "total_accepts")
    op.drop_column("tool_events", "total_rejects")

    # ── 8. CHECK constraints ─────────────────────────────────────────────────

    op.create_check_constraint(
        "ck_turns_quality_score", "turns",
        "quality_score >= 0 AND quality_score <= 1",
    )
    op.create_check_constraint(
        "ck_turns_prompt_chars", "turns",
        "prompt_chars > 0",
    )
    op.create_check_constraint(
        "ck_sessions_orchestration_score", "sessions",
        "orchestration_score IS NULL OR (orchestration_score >= 0 AND orchestration_score <= 1)",
    )
    op.create_check_constraint(
        "ck_sessions_turn_count", "sessions",
        "turn_count >= 0",
    )

    # ── 9. Production indexes ─────────────────────────────────────────────────

    # sessions hot paths
    op.create_index("idx_sessions_developer_started", "sessions", ["developer_id", "started_at"])
    op.create_index("idx_sessions_team_started",      "sessions", ["team_id",      "started_at"])
    op.create_index("idx_sessions_project_id",        "sessions", ["project_id"])
    op.create_index("idx_sessions_ended_at",          "sessions", ["ended_at"])

    # turns
    op.create_index("idx_turns_quality_score", "turns", ["quality_score"])
    op.create_index("idx_turns_created_at",    "turns", ["created_at"])

    # tool_events
    op.create_index("idx_tool_events_session_turn", "tool_events", ["session_id", "turn_index"])
    op.create_index("idx_tool_events_created_at",   "tool_events", ["created_at"])

    # developers
    op.create_index("idx_developers_email", "developers", ["email"])


def downgrade() -> None:
    # Indexes
    op.drop_index("idx_developers_email",        table_name="developers")
    op.drop_index("idx_tool_events_created_at",  table_name="tool_events")
    op.drop_index("idx_tool_events_session_turn",table_name="tool_events")
    op.drop_index("idx_turns_created_at",        table_name="turns")
    op.drop_index("idx_turns_quality_score",     table_name="turns")
    op.drop_index("idx_sessions_ended_at",       table_name="sessions")
    op.drop_index("idx_sessions_project_id",     table_name="sessions")
    op.drop_index("idx_sessions_team_started",   table_name="sessions")
    op.drop_index("idx_sessions_developer_started", table_name="sessions")

    # CHECK constraints
    op.drop_constraint("ck_sessions_turn_count",         "sessions",    type_="check")
    op.drop_constraint("ck_sessions_orchestration_score","sessions",    type_="check")
    op.drop_constraint("ck_turns_prompt_chars",          "turns",       type_="check")
    op.drop_constraint("ck_turns_quality_score",         "turns",       type_="check")

    # Restore dropped columns
    op.add_column("tool_events", sa.Column("total_rejects", sa.Integer, default=0))
    op.add_column("tool_events", sa.Column("total_accepts", sa.Integer, default=0))
    op.add_column("tool_events", sa.Column("team_id",       sa.String(64)))
    op.add_column("tool_events", sa.Column("developer_id",  sa.String(64)))

    op.add_column("turns", sa.Column("team_id",      sa.String(64)))
    op.add_column("turns", sa.Column("developer_id", sa.String(64)))

    op.add_column("sessions", sa.Column("project_name",     sa.String(256)))
    op.add_column("sessions", sa.Column("project_url",      sa.Text))
    op.add_column("sessions", sa.Column("developer_email",  sa.String(256)))
    op.add_column("sessions", sa.Column("developer_name",   sa.String(256)))

    op.alter_column("sessions", "turn_count", new_column_name="turns")
    op.drop_column("sessions", "updated_at")
    op.drop_column("sessions", "project_id")

    op.drop_table("projects")
    op.drop_table("teams")
    op.drop_table("developers")
