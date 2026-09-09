from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from bot.channels.email.filters import parse_filter, post_filter
from bot.channels.email.reader import MailboxReader, MailHeader
from bot.llm.base import ChatMessage, LLMError
from bot.llm.chain import LLMChain, default_chain
from bot.storage.models import Email

logger = logging.getLogger(__name__)

_DIGEST_PROMPT = (
    "Write a short plain-text digest of these emails for a Telegram message. "
    "Group by sender. One line per email: · <subject> (<date>). "
    "Start with a one-line count. No markdown.\n\nEMAILS:\n"
)

_REPLY_PROMPT = (
    "Draft a concise, polite reply to the email below. Plain text, no salutation placeholders "
    "like [Name] — use what you can infer. Do not send anything; this is a draft for review.\n\n"
)


class EmailService:
    def __init__(self, reader: MailboxReader | None = None, chain: LLMChain | None = None) -> None:
        self._reader = reader or MailboxReader()
        self._chain = chain or default_chain()

    async def digest(self, instruction: str, session: Session) -> str:
        spec = await parse_filter(instruction, self._chain)
        headers = self._reader.search(spec.criteria, limit=spec.limit)
        if not headers:
            return "No matching mail."

        if spec.post_filter:
            headers = await post_filter(headers, spec.post_filter, self._chain)
        if not headers:
            return "Nothing left after filtering."

        _persist(session, headers)
        return await self._summarize(headers)

    async def draft_reply(self, instruction: str, session: Session) -> str:
        """Find the message the instruction points at and return a draft reply (never sent)."""
        spec = await parse_filter(instruction, self._chain)
        headers = self._reader.search(spec.criteria, limit=max(spec.limit, 5))
        if not headers:
            return "No matching mail to reply to."

        target = headers[-1]  # newest match
        body = self._reader.fetch_body(target.uid)
        _persist(session, [target])

        prompt = (
            f"{_REPLY_PROMPT}"
            f"FROM: {target.from_addr}\nSUBJECT: {target.subject}\nDATE: {target.date_str}\n\n"
            f"{body or '(body unavailable)'}\n\n"
            f"REPLY GUIDANCE: {instruction}"
        )
        try:
            result = await self._chain.chat([ChatMessage("user", prompt)])
            draft = result.text.strip()
        except LLMError:
            return "Could not draft a reply right now."

        return f"Draft reply to \"{target.subject}\" ({target.from_addr}) — not sent:\n\n{draft}"

    async def _summarize(self, headers: list[MailHeader]) -> str:
        listing = "\n".join(f"{h.from_addr} / {h.subject} / {h.date_str}" for h in headers)
        try:
            result = await self._chain.chat([ChatMessage("user", _DIGEST_PROMPT + listing)])
            if result.text.strip():
                return result.text.strip()
        except LLMError:
            logger.warning("digest summarization failed, using plain format")
        return _plain_digest(headers)


def _persist(session: Session, headers: list[MailHeader]) -> None:
    for h in headers:
        session.execute(
            pg_insert(Email)
            .values(
                message_id=(h.message_id or h.uid)[:998],
                from_addr=h.from_addr[:320] or None,
                subject=h.subject or None,
                date=h.date,
                labels=[],
            )
            .on_conflict_do_nothing(index_elements=["message_id"])
        )


def _plain_digest(headers: list[MailHeader]) -> str:
    by_sender: dict[str, list[MailHeader]] = defaultdict(list)
    for h in headers:
        by_sender[h.from_addr or "(unknown sender)"].append(h)

    lines = [f"{len(headers)} message(s):"]
    for sender, items in by_sender.items():
        lines.append(f"\n{sender}")
        lines.extend(f"· {h.subject or '(no subject)'} ({h.date_str})" for h in items)
    return "\n".join(lines)
