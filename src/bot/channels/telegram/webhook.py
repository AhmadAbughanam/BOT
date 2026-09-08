from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy.orm import Session

from bot.channels.telegram.client import TelegramClient
from bot.config import get_settings
from bot.storage.models import Message

logger = logging.getLogger(__name__)


class Sender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> None: ...


async def handle_update(update: dict, session: Session, client: Sender | None = None) -> None:
    """Phase 1 behaviour: echo any text message back, persisting both sides."""
    client = client or TelegramClient()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    user_id = (message.get("from") or {}).get("id")
    text = message.get("text", "")

    allowed = get_settings().allowed_user_ids
    if allowed and user_id not in allowed:
        logger.warning("ignoring message from unauthorized user_id=%s", user_id)
        return

    session.add(Message(chat_id=chat_id, user_id=user_id, role="user", text=text))

    reply = f"echo: {text}" if text else "echo: (non-text message)"
    await client.send_message(chat_id, reply)

    session.add(Message(chat_id=chat_id, user_id=user_id, role="bot", text=reply))
