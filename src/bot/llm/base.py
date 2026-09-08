from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResult:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    provider: str
    model: str
    tokens: int = 0


class LLMError(Exception):
    """Any provider failure."""


class RateLimitError(LLMError):
    """Provider refused for quota / rate-limit / auth reasons (HTTP 429/401/403).

    The chain treats this as "try the next provider".
    """


class LLMProvider(Protocol):
    name: str

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult: ...


class EmbeddingProvider(Protocol):
    name: str

    async def embed(self, texts: list[str], model: str) -> EmbeddingResult: ...
