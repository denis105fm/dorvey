"""Add description, restrictions, recommendations to offers (full picture from Zeydoo).

Revision ID: 012
Revises: 011
Create Date: 2025-02-20

"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("offers", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("offers", sa.Column("restrictions", sa.Text(), nullable=True))
    op.add_column("offers", sa.Column("recommendations", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("offers", "recommendations")
    op.drop_column("offers", "restrictions")
    op.drop_column("offers", "description")
