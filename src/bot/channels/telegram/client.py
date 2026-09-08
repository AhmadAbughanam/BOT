from __future__ import annotations

import httpx

from bot.config import get_settings

API_ROOT = "https://api.telegram.org"


class TelegramClient:
    """Thin wrapper over the Telegram Bot HTTP API — only what phase 1 needs."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token or get_settings().telegram_bot_token

    @property
    def _base(self) -> str:
        return f"{API_ROOT}/bot{self._token}"

    async def send_message(self, chat_id: int, text: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            resp.raise_for_status()

    async def set_webhook(self, url: str, secret_token: str | None = None) -> dict:
        payload: dict = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{self._base}/setWebhook", json=payload)
            resp.raise_for_status()
            return resp.json()
