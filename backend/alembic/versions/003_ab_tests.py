"""Add doorway_ab_variants for A/B testing

Revision ID: 003
Revises: 002
Create Date: 2025-02-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doorway_ab_variants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("doorway_id", sa.Integer(), sa.ForeignKey("doorways.id"), nullable=False),
        sa.Column("variant", sa.String(10), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.String(500), nullable=True),
        sa.Column("impressions", sa.Integer(), server_default="0"),
        sa.Column("clicks", sa.Integer(), server_default="0"),
        sa.Column("conversions", sa.Integer(), server_default="0"),
        sa.Column("is_winner", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("doorway_ab_variants")
