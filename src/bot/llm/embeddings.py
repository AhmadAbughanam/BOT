from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from bot.llm.base import EmbeddingProvider, EmbeddingResult, LLMError, RateLimitError

logger = logging.getLogger(__name__)

ProviderFactory = Callable[[str], EmbeddingProvider]


@dataclass
class EmbedSpec:
    provider: str
    model: str


class EmbeddingChain:
    """Like LLMChain, but for `embed`. Falls through on rate-limit / provider errors."""

    def __init__(self, specs: list[EmbedSpec], *, factory: ProviderFactory | None = None) -> None:
        if not specs:
            raise ValueError("EmbeddingChain needs at least one spec")
        self._specs = specs
        if factory is not None:
            self._factory = factory
        else:
            from bot.llm.providers import build_provider

            self._factory = build_provider

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        errors: list[str] = []
        for spec in self._specs:
            provider = self._factory(spec.provider)
            try:
                return await provider.embed(texts, spec.model)
            except (RateLimitError, LLMError) as exc:
                logger.warning("embedding provider %s failed: %s", spec.provider, exc)
                errors.append(str(exc))
        raise LLMError("all embedding providers exhausted: " + " | ".join(errors))


def default_embedding_chain() -> EmbeddingChain | None:
    from bot.llm.loader import load_embeddings

    specs = load_embeddings()
    return EmbeddingChain(specs) if specs else None
