from __future__ import annotations

import httpx

from bot.llm.base import ChatMessage, ChatResult, EmbeddingResult, LLMError


class OllamaProvider:
    """Local fallback. Reached only when every hosted provider in the chain is exhausted."""

    name = "ollama"

    def __init__(self, host: str = "http://localhost:11434") -> None:
        self._host = host.rstrip("/")

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult:
        options: dict = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self._host}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": m.role, "content": m.content} for m in messages],
                        "stream": False,
                        "options": options,
                    },
                )
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name}: {exc}") from exc

        if resp.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        try:
            text = data["message"]["content"]
        except KeyError as exc:
            raise LLMError(f"{self.name}: unexpected response shape: {data}") from exc

        return ChatResult(
            text=text,
            provider=self.name,
            model=model,
            tokens_in=data.get("prompt_eval_count", 0),
            tokens_out=data.get("eval_count", 0),
        )

    async def embed(self, texts: list[str], model: str) -> EmbeddingResult:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self._host}/api/embed",
                    json={"model": model, "input": texts},
                )
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name}: {exc}") from exc

        if resp.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        try:
            vectors = data["embeddings"]
        except KeyError as exc:
            raise LLMError(f"{self.name}: unexpected embeddings response: {data}") from exc

        return EmbeddingResult(
            vectors=vectors,
            provider=self.name,
            model=model,
            tokens=data.get("prompt_eval_count", 0),
        )
