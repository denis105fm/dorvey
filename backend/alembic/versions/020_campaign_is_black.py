"""Add campaigns.is_black for black doorways.

Revision ID: 020
Revises: 019
Create Date: 2026

"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("campaigns", sa.Column("is_black", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("campaigns", "is_black")
