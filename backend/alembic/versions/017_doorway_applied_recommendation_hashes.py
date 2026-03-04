"""Store applied recommendation hashes so we don't suggest them again.

Revision ID: 017
Revises: 016
Create Date: 2025-03-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "doorways",
        sa.Column("applied_recommendation_hashes", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )


def downgrade():
    op.drop_column("doorways", "applied_recommendation_hashes")
