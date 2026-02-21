"""Add region and source to keywords.

Revision ID: 013
Revises: 012
Create Date: 2025-02-20

"""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("keywords", sa.Column("region", sa.String(10), nullable=True))
    op.add_column("keywords", sa.Column("source", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("keywords", "source")
    op.drop_column("keywords", "region")
