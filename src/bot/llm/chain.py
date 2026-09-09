from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass

from sqlalchemy.orm import Session

from bot.llm.base import ChatMessage, ChatResult, LLMError, LLMProvider, RateLimitError
from bot.llm.usage import record_usage, requests_today

logger = logging.getLogger(__name__)

ProviderFactory = Callable[[str], LLMProvider]
SessionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass
class ProviderSpec:
    provider: str
    model: str
    rpm: int | None = None
    rpd: int | None = None


class LLMChain:
    """Tries each provider in order; falls through on RateLimitError / LLMError.

    When a session factory is supplied, per-provider usage is recorded and the
    daily cap (`rpd`) is checked up front so a known-exhausted provider is skipped
    without a wasted request.
    """

    def __init__(
        self,
        specs: list[ProviderSpec],
        *,
        factory: ProviderFactory | None = None,
        session_factory: SessionFactory | None = None,
    ) -> None:
        if not specs:
            raise ValueError("LLMChain needs at least one provider spec")
        self._specs = specs
        self._session_factory = session_factory
        if factory is not None:
            self._factory = factory
        else:
            from bot.llm.providers import build_provider

            self._factory = build_provider

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult:
        errors: list[str] = []
        for spec in self._specs:
            if self._rpd_exhausted(spec):
                errors.append(f"{spec.provider}: daily cap ({spec.rpd}) reached")
                continue

            provider = self._factory(spec.provider)
            try:
                result = await provider.chat(
                    messages, spec.model, temperature=temperature, max_tokens=max_tokens
                )
            except (RateLimitError, LLMError) as exc:
                logger.warning("provider %s failed, falling through: %s", spec.provider, exc)
                errors.append(str(exc))
                continue

            self._record(spec, result)
            return result

        raise LLMError("all providers exhausted: " + " | ".join(errors))

    def _rpd_exhausted(self, spec: ProviderSpec) -> bool:
        if not spec.rpd or self._session_factory is None:
            return False
        with self._session_factory() as session:
            return requests_today(session, spec.provider, spec.model) >= spec.rpd

    def _record(self, spec: ProviderSpec, result: ChatResult) -> None:
        if self._session_factory is None:
            return
        with self._session_factory() as session:
            record_usage(session, spec.provider, spec.model, result.tokens_in, result.tokens_out)


@contextmanager
def _managed(session_local):
    session = session_local()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def default_chain() -> LLMChain:
    """Build the chain from config, wired to the app's session factory for usage tracking."""
    from bot.llm.loader import load_chain
    from bot.storage.db import SessionLocal

    return LLMChain(
        load_chain(),
        session_factory=lambda: _managed(SessionLocal),
    )


def chain_for_model(spec: str) -> LLMChain:
    """Single-provider chain from a ``"provider:model"`` string (used for `loop.judge_model`)."""
    provider, _, model = spec.partition(":")
    if not provider or not model:
        raise ValueError(f"expected 'provider:model', got {spec!r}")
    from bot.storage.db import SessionLocal

    return LLMChain(
        [ProviderSpec(provider=provider, model=model)],
        session_factory=lambda: _managed(SessionLocal),
    )
