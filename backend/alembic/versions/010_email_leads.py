"""Email leads capture for remarketing.

Revision ID: 010
Revises: 009
Create Date: 2025-02-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def _table_exists(conn, name):
    return name in reflection.Inspector.from_engine(conn).get_table_names()


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, "email_leads"):
        op.create_table(
            "email_leads",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("email", sa.String(255), nullable=False, index=True),
            sa.Column("visitor_id", sa.String(64), nullable=True, index=True),
            sa.Column("doorway_id", sa.Integer(), sa.ForeignKey("doorways.id", ondelete="CASCADE"), nullable=False),
            sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
    # Idempotent: create only indexes that don't exist (email/visitor_id indexes come from create_table index=True)
    inspector = reflection.Inspector.from_engine(conn)
    existing = {i["name"] for i in inspector.get_indexes("email_leads")}
    for idx, cols in [
        ("ix_email_leads_campaign_id", ["campaign_id"]),
        ("ix_email_leads_doorway_id", ["doorway_id"]),
    ]:
        if idx not in existing:
            op.create_index(idx, "email_leads", cols)


def downgrade():
    op.drop_table("email_leads")
