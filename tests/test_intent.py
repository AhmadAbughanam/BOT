from __future__ import annotations

from bot.core.intent import classify_intent
from bot.llm.base import ChatResult


class OneShotChain:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.calls = 0

    async def chat(self, messages, *, temperature=0.7, max_tokens=None) -> ChatResult:
        self.calls += 1
        return ChatResult(text=self._reply, provider="fake", model="fake")


async def test_slash_prefix_is_a_command_without_calling_the_model() -> None:
    chain = OneShotChain("{}")
    intent = await classify_intent("/help", chain)
    assert intent.kind == "command"
    assert chain.calls == 0


async def test_email_intent_carries_the_query() -> None:
    chain = OneShotChain('{"kind": "email", "query": "unread from bob"}')
    intent = await classify_intent("any unread from bob?", chain)
    assert intent.kind == "email"
    assert intent.query == "unread from bob"
    assert intent.action == "digest"  # defaulted when model omits it


async def test_email_draft_reply_action_is_kept() -> None:
    chain = OneShotChain('{"kind": "email", "query": "the last one from HR", "action": "draft_reply"}')
    intent = await classify_intent("draft a reply to the last HR email", chain)
    assert intent.kind == "email"
    assert intent.action == "draft_reply"


async def test_action_is_none_for_non_email_kinds() -> None:
    chain = OneShotChain('{"kind": "search", "query": "x", "action": "draft_reply"}')
    intent = await classify_intent("latest on x", chain)
    assert intent.kind == "search"
    assert intent.action is None


async def test_search_intent_is_recognized() -> None:
    chain = OneShotChain('{"kind": "search", "query": "latest on mars rover"}')
    intent = await classify_intent("what's the latest on the mars rover?", chain)
    assert intent.kind == "search"
    assert intent.query == "latest on mars rover"


async def test_unparseable_classification_defaults_to_question() -> None:
    chain = OneShotChain("no json here")
    intent = await classify_intent("what is the capital of France", chain)
    assert intent.kind == "question"
    assert intent.query is None
