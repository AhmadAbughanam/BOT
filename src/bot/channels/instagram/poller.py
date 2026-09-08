from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from bot.channels.instagram.client import DirectClient, DmMessage
from bot.core.formatting import for_instagram
from bot.core.router import route
from bot.storage.cursors import get_cursor, set_cursor
from bot.storage.models import Message

logger = logging.getLogger(__name__)

_CHANNEL = "instagram"
_FETCH_PER_THREAD = 15

Responder = Callable[[str, Session], Awaitable[str]]
CursorGet = Callable[[Session, str, str], str | None]
CursorSet = Callable[[Session, str, str, str], None]


def _new_messages(oldest_first: list[DmMessage], last_seen: str | None) -> list[DmMessage]:
    if last_seen is None:
        return oldest_first
    ids = [m.id for m in oldest_first]
    if last_seen in ids:
        return oldest_first[ids.index(last_seen) + 1 :]
    # cursor is older than the fetched window -> every fetched message is new
    return oldest_first


def _as_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def poll_once(
    session: Session,
    *,
    client: DirectClient,
    respond: Responder | None = None,
    allowed_ids: set[int] | None = None,
    cursor_get: CursorGet = get_cursor,
    cursor_set: CursorSet = set_cursor,
) -> int:
    """Process new inbound DMs across all inbox threads. Returns the reply count."""
    responder = respond or route
    allowed_ids = allowed_ids or set()
    me = client.self_user_id
    replies = 0

    for thread in client.inbox_threads():
        last_seen = cursor_get(session, _CHANNEL, thread.id)
        fetched = client.thread_messages(thread.id, amount=_FETCH_PER_THREAD)
        oldest_first = list(reversed(fetched))
        candidates = _new_messages(oldest_first, last_seen)
        if not candidates:
            continue

        for message in candidates:
            if message.user_id == me or not message.text.strip():
                continue
            sender = _as_int(message.user_id)
            if sender is None:
                continue
            if allowed_ids and sender not in allowed_ids:
                logger.warning("instagram: ignoring DM from unauthorized user_id=%s", message.user_id)
                continue

            session.add(Message(chat_id=sender, user_id=sender, role="user", text=message.text))
            reply = for_instagram(await responder(message.text, session))
            client.send_text(thread.id, reply)
            session.add(Message(chat_id=sender, user_id=sender, role="bot", text=reply))
            replies += 1

        cursor_set(session, _CHANNEL, thread.id, candidates[-1].id)

    return replies
