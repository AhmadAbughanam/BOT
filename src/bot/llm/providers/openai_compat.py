from __future__ import annotations

import httpx

from bot.llm.base import ChatMessage, ChatResult, LLMError, RateLimitError

_FALLTHROUGH_STATUS = {401, 403, 429}


class OpenAICompatProvider:
    """Base for providers that speak the OpenAI /chat/completions shape (Groq, OpenRouter, Cerebras)."""

    name = "openai-compat"
    base_url = ""

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult:
        if not self._key:
            raise RateLimitError(f"{self.name}: no API key configured")

        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._key}"},
            )

        if resp.status_code in _FALLTHROUGH_STATUS:
            raise RateLimitError(f"{self.name}: HTTP {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:  # pragma: no cover - defensive
            raise LLMError(f"{self.name}: unexpected response shape: {data}") from exc

        usage = data.get("usage") or {}
        return ChatResult(
            text=text,
            provider=self.name,
            model=model,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
        )


class GroqProvider(OpenAICompatProvider):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"


class OpenRouterProvider(OpenAICompatProvider):
    name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"


class CerebrasProvider(OpenAICompatProvider):
    name = "cerebras"
    base_url = "https://api.cerebras.ai/v1"
