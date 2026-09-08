from __future__ import annotations

import pytest

from bot.llm.base import EmbeddingResult, LLMError, RateLimitError
from bot.llm.embeddings import EmbeddingChain, EmbedSpec


class FakeEmbedProvider:
    def __init__(self, name: str, *, result: EmbeddingResult | None = None, error: Exception | None = None) -> None:
        self.name = name
        self._result = result
        self._error = error
        self.calls = 0

    async def embed(self, texts, model) -> EmbeddingResult:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


async def test_falls_through_to_next_embedding_provider() -> None:
    good = EmbeddingResult(vectors=[[0.1, 0.2]], provider="ollama", model="nomic")
    providers = {
        "gemini": FakeEmbedProvider("gemini", error=RateLimitError("gemini: HTTP 429")),
        "ollama": FakeEmbedProvider("ollama", result=good),
    }
    chain = EmbeddingChain(
        [EmbedSpec("gemini", "text-embedding-004"), EmbedSpec("ollama", "nomic")],
        factory=providers.__getitem__,
    )

    result = await chain.embed(["hello"])

    assert result.vectors == [[0.1, 0.2]]
    assert providers["gemini"].calls == 1
    assert providers["ollama"].calls == 1


async def test_raises_when_all_embedding_providers_fail() -> None:
    providers = {"gemini": FakeEmbedProvider("gemini", error=LLMError("gemini: boom"))}
    chain = EmbeddingChain([EmbedSpec("gemini", "m")], factory=providers.__getitem__)
    with pytest.raises(LLMError):
        await chain.embed(["x"])


def test_empty_spec_list_rejected() -> None:
    with pytest.raises(ValueError):
        EmbeddingChain([])
