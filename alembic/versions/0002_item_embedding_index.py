"""hnsw index on item_embeddings.embedding

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08
"""
from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_item_embeddings_hnsw",
        "item_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_item_embeddings_hnsw", table_name="item_embeddings")
