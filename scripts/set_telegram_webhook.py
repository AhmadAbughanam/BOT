"""Register the Telegram webhook.

Usage:
    python scripts/set_telegram_webhook.py https://your-host/telegram/webhook

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET from .env.
"""
from __future__ import annotations

import asyncio
import sys

from bot.channels.telegram.client import TelegramClient
from bot.config import get_settings


async def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: set_telegram_webhook.py <public-webhook-url>")
    secret = get_settings().telegram_webhook_secret or None
    result = await TelegramClient().set_webhook(sys.argv[1], secret)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
