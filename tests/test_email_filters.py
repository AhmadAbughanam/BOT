from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bot.channels.email.filters import parse_filter, post_filter
from bot.channels.email.reader import MailHeader
from bot.llm.base import ChatResult


class ReplyChain:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def chat(self, messages, *, temperature=0.7, max_tokens=None) -> ChatResult:
        return ChatResult(text=self._reply, provider="fake", model="fake")


def _header(i: int) -> MailHeader:
    return MailHeader(
        uid=str(i),
        message_id=f"<{i}@x>",
        from_addr=f"sender{i}@example.com",
        subject=f"subject {i}",
        date=datetime(2026, 9, 1, tzinfo=UTC),
    )


async def test_parse_filter_builds_criteria_and_clamps_limit() -> None:
    chain = ReplyChain(
        '{"since_days": 7, "unseen": true, "from_contains": "recruiter", '
        '"subject_contains": null, "limit": 500, "post_filter": "skip newsletters"}'
    )
    spec = await parse_filter("unread from recruiters this week, skip newsletters", chain)

    expected_since = datetime.now(UTC).date() - timedelta(days=7)
    assert spec.criteria.unseen is True
    assert spec.criteria.since == expected_since
    assert spec.criteria.from_contains == "recruiter"
    assert spec.limit == 100  # clamped from 500
    assert spec.post_filter == "skip newsletters"
    assert "UNSEEN" in spec.criteria.to_imap_string()
    assert 'FROM "recruiter"' in spec.criteria.to_imap_string()


async def test_parse_filter_falls_back_to_defaults_on_bad_json() -> None:
    spec = await parse_filter("anything", ReplyChain("sorry, no json"))
    assert spec.criteria.to_imap_string() == "ALL"
    assert spec.limit == 50
    assert spec.post_filter is None


async def test_post_filter_keeps_only_flagged_messages() -> None:
    headers = [_header(0), _header(1), _header(2)]
    chain = ReplyChain('[{"i": 0, "keep": true}, {"i": 1, "keep": false}, {"i": 2, "keep": true}]')

    kept = await post_filter(headers, "keep the important ones", chain)

    assert [h.uid for h in kept] == ["0", "2"]


async def test_post_filter_fails_open_on_bad_response() -> None:
    headers = [_header(0), _header(1)]
    kept = await post_filter(headers, "instruction", ReplyChain("not an array"))
    assert kept == headers
