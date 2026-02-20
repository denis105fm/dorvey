"""Add name, rate, amount, term to offers for comparison table.

Revision ID: 008
Revises: 007
Create Date: 2025-02-15

"""
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("offers", op.Column("name", op.String(255), nullable=True))
    op.add_column("offers", op.Column("rate", op.String(50), nullable=True))
    op.add_column("offers", op.Column("amount", op.String(50), nullable=True))
    op.add_column("offers", op.Column("term", op.String(50), nullable=True))


def downgrade():
    op.drop_column("offers", "term")
    op.drop_column("offers", "amount")
    op.drop_column("offers", "rate")
    op.drop_column("offers", "name")
