from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from bot.channels.email.reader import ImapCriteria, MailHeader
from bot.jsonutil import extract_json
from bot.llm.base import ChatMessage
from bot.llm.chain import LLMChain

logger = logging.getLogger(__name__)

_POST_FILTER_CAP = 40

_FILTER_PROMPT = (
    "Turn the user's mail request into JSON with exactly these fields "
    "(use null when the request does not mention them):\n"
    '{"since_days": int|null, "before_days": int|null, "unseen": bool, '
    '"from_contains": string|null, "subject_contains": string|null, '
    '"limit": int between 1 and 100, "post_filter": string|null}\n'
    '"post_filter" holds any fuzzy instruction IMAP cannot express, e.g. '
    '"skip newsletters", "only ones that need a reply".\n\n'
    "REQUEST:\n"
)

_POST_FILTER_PROMPT = (
    "Decide which emails to KEEP given the instruction. "
    'Reply with ONLY a JSON array of objects with integer "i" and boolean "keep".\n\n'
    "INSTRUCTION: "
)


@dataclass
class FilterSpec:
    criteria: ImapCriteria
    limit: int = 50
    post_filter: str | None = None


async def parse_filter(instruction: str, chain: LLMChain) -> FilterSpec:
    result = await chain.chat(
        [ChatMessage("user", _FILTER_PROMPT + instruction)], temperature=0.0
    )
    data = extract_json(result.text)
    if not isinstance(data, dict):
        logger.warning("filter parse failed, using defaults: %r", result.text[:120])
        data = {}

    today = datetime.now(UTC).date()
    since = _days_ago(today, data.get("since_days"))
    before = _days_ago(today, data.get("before_days"))
    limit = _clamp_int(data.get("limit"), default=50, low=1, high=100)

    criteria = ImapCriteria(
        unseen=bool(data.get("unseen")),
        since=since,
        before=before,
        from_contains=(data.get("from_contains") or None),
        subject_contains=(data.get("subject_contains") or None),
    )
    return FilterSpec(criteria=criteria, limit=limit, post_filter=(data.get("post_filter") or None))


async def post_filter(
    headers: list[MailHeader], instruction: str, chain: LLMChain
) -> list[MailHeader]:
    """Keep only the messages the model marks; fail open (keep all) on a bad response."""
    subset = headers[:_POST_FILTER_CAP]
    listing = "\n".join(
        f"{i}. {h.from_addr} / {h.subject} / {h.date_str}" for i, h in enumerate(subset)
    )
    prompt = f"{_POST_FILTER_PROMPT}{instruction}\n\nEMAILS:\n{listing}"
    result = await chain.chat([ChatMessage("user", prompt)], temperature=0.0)
    data = extract_json(result.text)
    if not isinstance(data, list):
        logger.warning("post-filter parse failed, keeping all %d message(s)", len(headers))
        return headers

    keep_idx = {
        d["i"]
        for d in data
        if isinstance(d, dict) and d.get("keep") and isinstance(d.get("i"), int)
    }
    kept = [h for i, h in enumerate(subset) if i in keep_idx]
    return kept + headers[_POST_FILTER_CAP:]


def _days_ago(today, value):
    if value in (None, "", False):
        return None
    try:
        return today - timedelta(days=int(value))
    except (TypeError, ValueError):
        return None


def _clamp_int(value, *, default: int, low: int, high: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, n))
