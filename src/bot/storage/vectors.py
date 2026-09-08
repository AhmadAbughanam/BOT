from __future__ import annotations

import logging
import math
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.llm.embeddings import EmbeddingChain
from bot.storage.models import Item, ItemEmbedding

logger = logging.getLogger(__name__)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def items_missing_embeddings(session: Session, items: list[Item]) -> list[Item]:
    ids = [i.id for i in items if i.id is not None]
    if not ids:
        return [i for i in items if i.id is not None]
    have = set(
        session.execute(
            select(ItemEmbedding.item_id).where(ItemEmbedding.item_id.in_(ids))
        ).scalars()
    )
    return [i for i in items if i.id is not None and i.id not in have]


def nearest(
    session: Session,
    vector: list[float],
    *,
    limit: int = 5,
    exclude_item_id: int | None = None,
) -> list[tuple[int, float]]:
    """Return (item_id, cosine_distance) for the closest stored embeddings."""
    distance = ItemEmbedding.embedding.cosine_distance(vector).label("distance")
    stmt = select(ItemEmbedding.item_id, distance)
    if exclude_item_id is not None:
        stmt = stmt.where(ItemEmbedding.item_id != exclude_item_id)
    stmt = stmt.order_by(distance).limit(limit)
    return [(row.item_id, float(row.distance)) for row in session.execute(stmt)]


def has_semantic_duplicate(session: Session, vector: list[float], threshold: float) -> bool:
    rows = nearest(session, vector, limit=1)
    return bool(rows) and rows[0][1] <= threshold


async def embed_and_store(session: Session, items: list[Item], chain: EmbeddingChain) -> int:
    """Embed the title of each item that lacks an embedding and insert the rows."""
    targets = items_missing_embeddings(session, items)
    if not targets:
        return 0
    result = await chain.embed([i.title or i.url for i in targets])
    for item, vector in zip(targets, result.vectors):
        session.add(ItemEmbedding(item_id=item.id, embedding=vector, model=result.model))
    return len(targets)


async def backfill_embeddings(session: Session, chain: EmbeddingChain, *, batch: int = 64) -> int:
    """Embed every `items` row that has no `item_embeddings` row yet."""
    pending = list(
        session.execute(
            select(Item).where(
                ~select(ItemEmbedding.item_id)
                .where(ItemEmbedding.item_id == Item.id)
                .exists()
            )
        ).scalars()
    )
    total = 0
    for start in range(0, len(pending), batch):
        total += await embed_and_store(session, pending[start : start + batch], chain)
    return total
