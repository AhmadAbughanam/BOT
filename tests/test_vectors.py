from __future__ import annotations

from dataclasses import dataclass

from bot.llm.base import EmbeddingResult
from bot.storage.models import Item, ItemEmbedding
from bot.storage.vectors import (
    cosine,
    embed_and_store,
    has_semantic_duplicate,
    items_missing_embeddings,
    nearest,
)


@dataclass
class Row:
    item_id: int
    distance: float


class FakeResult:
    def __init__(self, *, scalar_values=(), rows=()) -> None:
        self._scalars = list(scalar_values)
        self._rows = list(rows)

    def scalars(self):
        return self._scalars

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    def __init__(self, *, scalar_values=(), rows=()) -> None:
        self.added: list = []
        self._result = FakeResult(scalar_values=scalar_values, rows=rows)

    def add(self, obj) -> None:
        self.added.append(obj)

    def execute(self, _stmt):
        return self._result


def _item(i: int) -> Item:
    it = Item(title=f"t{i}", url=f"https://x/{i}")
    it.id = i
    return it


def test_cosine_basic() -> None:
    assert cosine([1, 0], [1, 0]) == 1.0
    assert cosine([1, 0], [0, 1]) == 0.0


def test_items_missing_embeddings_excludes_those_already_embedded() -> None:
    items = [_item(1), _item(2), _item(3)]
    session = FakeSession(scalar_values=[2])  # id 2 already has an embedding
    missing = items_missing_embeddings(session, items)
    assert [i.id for i in missing] == [1, 3]


def test_has_semantic_duplicate_respects_threshold() -> None:
    close = FakeSession(rows=[Row(item_id=9, distance=0.03)])
    far = FakeSession(rows=[Row(item_id=9, distance=0.4)])
    assert has_semantic_duplicate(close, [0.1, 0.2], 0.08) is True
    assert has_semantic_duplicate(far, [0.1, 0.2], 0.08) is False


def test_nearest_maps_rows_to_tuples() -> None:
    session = FakeSession(rows=[Row(item_id=1, distance=0.1), Row(item_id=2, distance=0.2)])
    assert nearest(session, [0.0, 1.0]) == [(1, 0.1), (2, 0.2)]


async def test_embed_and_store_adds_one_row_per_missing_item() -> None:
    items = [_item(1), _item(2)]
    session = FakeSession(scalar_values=[])  # none embedded yet

    class Chain:
        async def embed(self, texts):
            assert texts == ["t1", "t2"]
            return EmbeddingResult(vectors=[[0.1], [0.2]], provider="fake", model="m")

    count = await embed_and_store(session, items, Chain())

    assert count == 2
    assert all(isinstance(o, ItemEmbedding) for o in session.added)
    assert [(o.item_id, o.model) for o in session.added] == [(1, "m"), (2, "m")]
