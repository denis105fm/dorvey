"""Add target_geo to doorways for multi-country generation and indexing.

Revision ID: 018
Revises: 017
Create Date: 2025

When set, doorway content/language is for this geo (language from country preset).
Enables one campaign to have doorways for US, DE, PL etc. with correct lang and indexing.
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "doorways",
        sa.Column("target_geo", sa.String(10), nullable=True),
    )


def downgrade():
    op.drop_column("doorways", "target_geo")
