"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from bot.config import get_settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBED_DIM = get_settings().embed_dim


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("subcategory", sa.String(64), nullable=False),
        sa.Column("search_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("subcategory", sa.String(64), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_items_category", "items", ["category", "subcategory"])

    op.create_table(
        "item_embeddings",
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "emails",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.String(998), nullable=False, unique=True),
        sa.Column("from_addr", sa.String(320), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("labels", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_chat_id", "messages", ["chat_id", "created_at"])

    op.create_table(
        "briefs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("task", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("cited_item_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("cited_email_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "loop_traces",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("task", sa.String(64), nullable=True),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("draft", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=True),
        sa.Column("critique", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_loop_traces_run_id", "loop_traces", ["run_id"])

    op.create_table(
        "llm_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("provider", "model", "day", name="uq_llm_usage_provider_model_day"),
    )


def downgrade() -> None:
    for table in (
        "llm_usage",
        "loop_traces",
        "briefs",
        "messages",
        "emails",
        "item_embeddings",
        "items",
        "sources",
    ):
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS vector")
