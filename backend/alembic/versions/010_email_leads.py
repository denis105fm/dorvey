"""Email leads capture for remarketing.

Revision ID: 010
Revises: 009
Create Date: 2025-02-17

"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_leads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("visitor_id", sa.String(64), nullable=True, index=True),
        sa.Column("doorway_id", sa.Integer(), sa.ForeignKey("doorways.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_email_leads_campaign_id", "email_leads", ["campaign_id"])
    op.create_index("ix_email_leads_doorway_id", "email_leads", ["doorway_id"])
    op.create_index("ix_email_leads_email", "email_leads", ["email"])


def downgrade():
    op.drop_table("email_leads")
