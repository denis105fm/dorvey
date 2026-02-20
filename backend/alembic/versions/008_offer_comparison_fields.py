"""Add name, rate, amount, term to offers for comparison table.

Revision ID: 008
Revises: 007
Create Date: 2025-02-15

"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("offers", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("offers", sa.Column("rate", sa.String(50), nullable=True))
    op.add_column("offers", sa.Column("amount", sa.String(50), nullable=True))
    op.add_column("offers", sa.Column("term", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("offers", "term")
    op.drop_column("offers", "amount")
    op.drop_column("offers", "rate")
    op.drop_column("offers", "name")
