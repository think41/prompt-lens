"""Add developer_email, project_url, project_name to sessions

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("developer_email", sa.String(256), nullable=True))
    op.add_column("sessions", sa.Column("project_url", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("project_name", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "project_name")
    op.drop_column("sessions", "project_url")
    op.drop_column("sessions", "developer_email")
