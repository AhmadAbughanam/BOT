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


@dataclass
class Intent:
    kind: IntentKind
    query: str | None = None


_PROMPT = (
    "Classify the user message. Reply with ONLY JSON: "
    '{"kind": "email" or "search" or "question", "query": "<the request, or null>"}\n'
    '"email"    = the user wants to read, filter, or summarize their mailbox / inbox.\n'
    '"search"   = the user wants current news or up-to-date info on a topic '
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
    return Intent(kind=kind, query=query if isinstance(query, str) and query.strip() else None)
