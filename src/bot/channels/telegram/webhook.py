from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from sqlalchemy.orm import Session

from bot.channels.telegram.client import TelegramClient
from bot.config import get_settings
from bot.llm.chain import default_chain
from bot.llm.loader import load_loop_defaults
from bot.refine.loop import RefineConfig, refine
from bot.storage.models import Message

logger = logging.getLogger(__name__)

Responder = Callable[[str, Session], Awaitable[str]]

COMMANDS: dict[str, str] = {
    "/start": "Hi. Send me a question and I'll answer after a self-review pass.",
    "/help": "Just type a question. Commands: /start, /help.",
}


class Sender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> None: ...


async def default_respond(question: str, session: Session) -> str:
    """Answer a free-text message via the LLM chain + refine loop."""
    cfg = RefineConfig.from_mapping(load_loop_defaults())
    result = await refine(question, default_chain(), cfg, task="chat", session=session)
    return result.answer


async def handle_update(
    update: dict,
    session: Session,
    *,
    client: Sender | None = None,
    respond: Responder | None = None,
) -> None:
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

    if not text:
        reply = "I can only handle text messages for now."
    elif text.startswith("/"):
        reply = COMMANDS.get(text.split()[0], "Unknown command. Try /help.")
    else:
        responder = respond or default_respond
        reply = await responder(text, session)

    await client.send_message(chat_id, reply)
    session.add(Message(chat_id=chat_id, user_id=user_id, role="bot", text=reply))
