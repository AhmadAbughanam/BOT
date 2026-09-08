from __future__ import annotations

from bot.config import get_settings
from bot.llm.base import LLMProvider
from bot.llm.providers.gemini import GeminiProvider
from bot.llm.providers.ollama import OllamaProvider
from bot.llm.providers.openai_compat import (
    CerebrasProvider,
    GroqProvider,
    OpenRouterProvider,
)


def build_provider(name: str) -> LLMProvider:
    """Construct a provider by its config name, pulling credentials from settings."""
    s = get_settings()
    match name:
        case "groq":
            return GroqProvider(s.groq_api_key)
        case "openrouter":
            return OpenRouterProvider(s.openrouter_api_key)
        case "cerebras":
            return CerebrasProvider(s.cerebras_api_key)
        case "gemini":
            return GeminiProvider(s.gemini_api_key)
        case "ollama":
            return OllamaProvider(s.ollama_host)
        case _:
            raise ValueError(f"unknown llm provider: {name!r}")


__all__ = [
    "build_provider",
    "GroqProvider",
    "OpenRouterProvider",
    "CerebrasProvider",
    "GeminiProvider",
    "OllamaProvider",
]
