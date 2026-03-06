"""Server metrics table for VPS monitoring.

Revision ID: 019
Revises: 018
Create Date: 2025

"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "server_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("load_1", sa.Float(), nullable=True),
        sa.Column("load_5", sa.Float(), nullable=True),
        sa.Column("load_15", sa.Float(), nullable=True),
        sa.Column("mem_total_kb", sa.BigInteger(), nullable=True),
        sa.Column("mem_available_kb", sa.BigInteger(), nullable=True),
        sa.Column("disk_total_kb", sa.BigInteger(), nullable=True),
        sa.Column("disk_used_kb", sa.BigInteger(), nullable=True),
        sa.Column("nproc", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_server_metrics_server_id", "server_metrics", ["server_id"])
    op.create_index("ix_server_metrics_created_at", "server_metrics", ["created_at"])


def downgrade():
    op.drop_index("ix_server_metrics_created_at", "server_metrics")
    op.drop_index("ix_server_metrics_server_id", "server_metrics")
    op.drop_table("server_metrics")
