"""Add orchestration_score and session_flags to sessions

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("orchestration_score", sa.Float(), nullable=True))
    op.add_column("sessions", sa.Column("session_flags", ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "session_flags")
    op.drop_column("sessions", "orchestration_score")
