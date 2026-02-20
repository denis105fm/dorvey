"""Add pause_reason to doorways.

Revision ID: 011
Revises: 010
Create Date: 2025-02-20

"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("doorways", sa.Column("pause_reason", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("doorways", "pause_reason")
