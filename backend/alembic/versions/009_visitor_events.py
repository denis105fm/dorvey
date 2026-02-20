"""Visitor capture and push subscriptions for remarketing.

Revision ID: 009
Revises: 008
Create Date: 2025-02-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "visitor_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("visitor_id", sa.String(64), nullable=False, index=True),
        sa.Column("doorway_id", sa.Integer(), sa.ForeignKey("doorways.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),  # visit, click, push_subscribe
        sa.Column("meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_visitor_events_doorway_id", "visitor_events", ["doorway_id"])
    op.create_index("ix_visitor_events_campaign_id", "visitor_events", ["campaign_id"])
    op.create_index("ix_visitor_events_created_at", "visitor_events", ["created_at"])

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("visitor_id", sa.String(64), nullable=False, index=True),
        sa.Column("doorway_id", sa.Integer(), sa.ForeignKey("doorways.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_push_subscriptions_visitor_id", "push_subscriptions", ["visitor_id"])


def downgrade():
    op.drop_table("push_subscriptions")
    op.drop_table("visitor_events")
