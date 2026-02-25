"""Doorway source metrics (traffic by utm_source) for ROI by source.

Revision ID: 016
Revises: 015
Create Date: 2025-02-21

"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "doorway_source_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("doorway_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("clicks", sa.Integer(), server_default="0"),
        sa.Column("conversions", sa.Integer(), server_default="0"),
        sa.Column("revenue", sa.Float(), server_default="0"),
        sa.ForeignKeyConstraint(["doorway_id"], ["doorways.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doorway_source_metrics_doorway_id", "doorway_source_metrics", ["doorway_id"])
    op.create_index("ix_doorway_source_metrics_date", "doorway_source_metrics", ["date"])
    op.create_index("ix_doorway_source_metrics_source", "doorway_source_metrics", ["source"])
    op.create_index(
        "ix_doorway_source_metrics_doorway_date_source",
        "doorway_source_metrics",
        ["doorway_id", "date", "source"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_doorway_source_metrics_doorway_date_source", "doorway_source_metrics")
    op.drop_index("ix_doorway_source_metrics_source", "doorway_source_metrics")
    op.drop_index("ix_doorway_source_metrics_date", "doorway_source_metrics")
    op.drop_index("ix_doorway_source_metrics_doorway_id", "doorway_source_metrics")
    op.drop_table("doorway_source_metrics")
