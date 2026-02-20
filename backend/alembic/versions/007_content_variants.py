"""Add content_variants to doorways for A/B content.

Revision ID: 007
Revises: 006
Create Date: 2025-02-15

"""
from alembic import op
from sqlalchemy import text

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("doorways", op.Column("content_variants", op.dialects.postgresql.JSONB(), nullable=True))
    op.execute(text("UPDATE doorways SET content_variants = '[]'::jsonb WHERE content_variants IS NULL"))


def downgrade():
    op.drop_column("doorways", "content_variants")
