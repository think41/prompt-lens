"""Add privacy-off columns: developer_name, cwd, prompt_text, file_path

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("developer_name", sa.String(256), nullable=True))
    op.add_column("sessions", sa.Column("cwd", sa.Text(), nullable=True))
    op.add_column("turns", sa.Column("prompt_text", sa.Text(), nullable=True))
    op.add_column("tool_events", sa.Column("file_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tool_events", "file_path")
    op.drop_column("turns", "prompt_text")
    op.drop_column("sessions", "cwd")
    op.drop_column("sessions", "developer_name")
