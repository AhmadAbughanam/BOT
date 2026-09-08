from __future__ import annotations

import httpx

from bot.llm.base import (
    ChatMessage,
    ChatResult,
    EmbeddingResult,
    LLMError,
    RateLimitError,
)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
_FALLTHROUGH_STATUS = {401, 403, 429}


class GeminiProvider:
    name = "gemini"

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

        system_parts = [m.content for m in messages if m.role == "system"]
        contents = [
            {
                "role": "model" if m.role == "assistant" else "user",
                "parts": [{"text": m.content}],
            }
            for m in messages
            if m.role != "system"
        ]

        payload: dict = {"contents": contents, "generationConfig": {"temperature": temperature}}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{_API_ROOT}/models/{model}:generateContent",
                params={"key": self._key},
                json=payload,
            )

        if resp.status_code in _FALLTHROUGH_STATUS:
            raise RateLimitError(f"{self.name}: HTTP {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"{self.name}: unexpected response shape: {data}") from exc

        usage = data.get("usageMetadata") or {}
        return ChatResult(
            text=text,
            provider=self.name,
            model=model,
            tokens_in=usage.get("promptTokenCount", 0),
            tokens_out=usage.get("candidatesTokenCount", 0),
        )

    async def embed(self, texts: list[str], model: str) -> EmbeddingResult:
        if not self._key:
            raise RateLimitError(f"{self.name}: no API key configured")

        requests = [
            {"model": f"models/{model}", "content": {"parts": [{"text": text}]}}
            for text in texts
        ]
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{_API_ROOT}/models/{model}:batchEmbedContents",
                params={"key": self._key},
                json={"requests": requests},
            )

        if resp.status_code in _FALLTHROUGH_STATUS:
            raise RateLimitError(f"{self.name}: HTTP {resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        try:
            vectors = [row["values"] for row in data["embeddings"]]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"{self.name}: unexpected embeddings response: {data}") from exc

        return EmbeddingResult(vectors=vectors, provider=self.name, model=model)
