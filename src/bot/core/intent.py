from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from bot.jsonutil import extract_json
from bot.llm.base import ChatMessage
from bot.llm.chain import LLMChain

logger = logging.getLogger(__name__)

IntentKind = Literal["command", "email", "search", "question"]

_MODEL_KINDS = ("email", "search", "question")
_EMAIL_ACTIONS = ("digest", "draft_reply")


@dataclass
class Intent:
    kind: IntentKind
    query: str | None = None
    action: str | None = None  # for kind == "email": "digest" | "draft_reply"


_PROMPT = (
    "Classify the user message. Reply with ONLY JSON: "
    '{"kind": "email"|"search"|"question", "query": "<the request, or null>", '
    '"action": "digest"|"draft_reply"|null}\n'
    '"email"    = wants to read, filter, or summarize their mailbox / inbox. '
    'Set "action" to "draft_reply" if they ask to reply to / respond to / answer an email, '
    'otherwise "digest".\n'
    '"search"   = wants current news or up-to-date info on a topic '
    '(headlines, "latest on X", "what happened with Y").\n'
    '"question" = anything else (general knowledge, advice, chit-chat).\n\n'
    "MESSAGE:\n"
)


async def classify_intent(text: str, chain: LLMChain) -> Intent:
    text = text.strip()
    if text.startswith("/"):
        return Intent(kind="command")

    result = await chain.chat([ChatMessage("user", _PROMPT + text)], temperature=0.0)
    data = extract_json(result.text)
    if not isinstance(data, dict) or data.get("kind") not in _MODEL_KINDS:
        logger.info("intent classification unclear, defaulting to question: %r", result.text[:120])
        return Intent(kind="question")

    kind: IntentKind = data["kind"]
    query = data.get("query")
    action = data.get("action")
    if kind != "email" or action not in _EMAIL_ACTIONS:
        action = "digest" if kind == "email" else None

    return Intent(
        kind=kind,
        query=query if isinstance(query, str) and query.strip() else None,
        action=action,
    )
