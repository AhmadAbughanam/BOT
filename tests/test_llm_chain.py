from __future__ import annotations

import pytest

from bot.llm.base import ChatMessage, ChatResult, LLMError, RateLimitError
from bot.llm.chain import LLMChain, ProviderSpec


class FakeProvider:
    def __init__(self, name: str, *, result: ChatResult | None = None, error: Exception | None = None) -> None:
        self.name = name
        self._result = result
        self._error = error
        self.calls = 0

    async def chat(self, messages, model, *, temperature=0.7, max_tokens=None) -> ChatResult:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


def _msgs() -> list[ChatMessage]:
    return [ChatMessage("user", "hi")]


async def test_falls_through_ratelimited_provider_to_next() -> None:
    good = ChatResult(text="ok", provider="gemini", model="m2")
    providers = {
        "groq": FakeProvider("groq", error=RateLimitError("groq: HTTP 429")),
        "gemini": FakeProvider("gemini", result=good),
    }
    chain = LLMChain(
        [ProviderSpec("groq", "m1"), ProviderSpec("gemini", "m2")],
        factory=providers.__getitem__,
    )

    result = await chain.chat(_msgs())

    assert result.text == "ok"
    assert providers["groq"].calls == 1
    assert providers["gemini"].calls == 1


async def test_raises_when_all_providers_exhausted() -> None:
    providers = {
        "groq": FakeProvider("groq", error=RateLimitError("groq: HTTP 429")),
        "ollama": FakeProvider("ollama", error=LLMError("ollama: connection refused")),
    }
    chain = LLMChain(
        [ProviderSpec("groq", "m1"), ProviderSpec("ollama", "m2")],
        factory=providers.__getitem__,
    )

    with pytest.raises(LLMError) as excinfo:
        await chain.chat(_msgs())

    assert "groq: HTTP 429" in str(excinfo.value)
    assert "ollama: connection refused" in str(excinfo.value)


async def test_empty_spec_list_rejected() -> None:
    with pytest.raises(ValueError):
        LLMChain([])
