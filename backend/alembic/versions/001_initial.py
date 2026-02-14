"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("two_fa_secret", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), server_default="22"),
        sa.Column("user", sa.String(100), nullable=False),
        sa.Column("auth_type", sa.String(20), server_default="ssh_key"),
        sa.Column("auth_data", sa.String(500), nullable=True),
        sa.Column("path", sa.String(500), server_default="/var/www/html"),
        sa.Column("ssl_auto", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("affiliate_url", sa.Text(), nullable=True),
        sa.Column("affiliate_rules", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(10), server_default="ru"),
        sa.Column("locale", sa.String(10), server_default="ru-RU"),
        sa.Column("region", sa.String(10), server_default="RU"),
        sa.Column("currency", sa.String(5), server_default="RUB"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "domains",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("ssl_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_domains_domain", "domains", ["domain"], unique=True)

    op.create_table(
        "doorways",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("domains.id"), nullable=False),
        sa.Column("path", sa.String(500), server_default="/"),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.String(500), nullable=True),
        sa.Column("cloaking_rules", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(30), server_default="draft"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("deployed_at", sa.DateTime(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "doorway_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("doorway_id", sa.Integer(), sa.ForeignKey("doorways.id"), nullable=False),
        sa.Column("content_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "doorway_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("doorway_id", sa.Integer(), sa.ForeignKey("doorways.id"), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("impressions", sa.Integer(), server_default="0"),
        sa.Column("clicks", sa.Integer(), server_default="0"),
        sa.Column("ctr", sa.Float(), server_default="0"),
        sa.Column("avg_position", sa.Float(), server_default="0"),
        sa.Column("conversions", sa.Integer(), server_default="0"),
        sa.Column("revenue", sa.Float(), server_default="0"),
    )

    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("keyword", sa.String(500), nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column("volume", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(30), server_default="page"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("variables", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("templates")
    op.drop_table("keywords")
    op.drop_table("doorway_metrics")
    op.drop_table("doorway_versions")
    op.drop_table("doorways")
    op.drop_table("domains")
    op.drop_table("campaigns")
    op.drop_table("servers")
    op.drop_table("users")
