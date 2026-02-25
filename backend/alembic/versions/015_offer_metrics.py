"""Offer metrics table for ROI-based offer selection.

Revision ID: 015
Revises: 014
Create Date: 2025-02-21

"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "offer_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("clicks", sa.Integer(), server_default="0"),
        sa.Column("conversions", sa.Integer(), server_default="0"),
        sa.Column("revenue", sa.Float(), server_default="0"),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offer_metrics_offer_id", "offer_metrics", ["offer_id"])
    op.create_index("ix_offer_metrics_date", "offer_metrics", ["date"])


def downgrade():
    op.drop_index("ix_offer_metrics_date", "offer_metrics")
    op.drop_index("ix_offer_metrics_offer_id", "offer_metrics")
    op.drop_table("offer_metrics")
