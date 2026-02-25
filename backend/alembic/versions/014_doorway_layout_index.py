"""Add layout_index to doorways for winner layout override.

Revision ID: 014
Revises: 013
Create Date: 2025-02-21

"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("doorways", sa.Column("layout_index", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("doorways", "layout_index")
