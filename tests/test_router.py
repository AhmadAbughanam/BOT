from __future__ import annotations

from bot.core.router import route
from bot.llm.base import ChatResult
from bot.storage.models import Item


class ScriptedChain:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)

    async def chat(self, messages, *, temperature=0.7, max_tokens=None) -> ChatResult:
        return ChatResult(text=self._replies.pop(0), provider="fake", model="fake")


class FakeEmailService:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.draft_calls: list[str] = []

    async def digest(self, instruction: str, session) -> str:
        self.calls.append(instruction)
        return "DIGEST"

    async def draft_reply(self, instruction: str, session) -> str:
        self.draft_calls.append(instruction)
        return "DRAFT"


class FakeScrapingService:
    def __init__(self, items: list[Item]) -> None:
        self._items = items
        self.calls: list[str] = []

    async def collect(self, query: str, session, **kwargs) -> list[Item]:
        self.calls.append(query)
        return self._items


async def test_command_is_answered_without_the_model() -> None:
    reply = await route("/start", session=None, chain=ScriptedChain([]))
    assert reply.startswith("Hi.")


async def test_email_intent_dispatches_to_the_email_service() -> None:
    chain = ScriptedChain(['{"kind": "email", "query": "unread today"}'])
    svc = FakeEmailService()

    reply = await route("anything new in my inbox?", session=None, chain=chain, email_service=svc)

    assert reply == "DIGEST"
    assert svc.calls == ["unread today"]


async def test_email_draft_reply_action_routes_to_draft_reply() -> None:
    chain = ScriptedChain(
        ['{"kind": "email", "query": "the last one from HR", "action": "draft_reply"}']
    )
    svc = FakeEmailService()

    reply = await route("reply to the HR email", session=None, chain=chain, email_service=svc)

    assert reply == "DRAFT"
    assert svc.draft_calls == ["the last one from HR"]
    assert svc.calls == []


async def test_search_intent_scrapes_then_summarizes_with_context() -> None:
    chain = ScriptedChain(
        [
            '{"kind": "search", "query": "eu ai act"}',
            "The EU AI Act entered into force in 2024.",
            '{"score": 0.95, "critique": "grounded"}',
        ]
    )
    svc = FakeScrapingService([Item(title="EU AI Act explainer", url="https://x.example/ai-act")])

    reply = await route("latest on the eu ai act", session=None, chain=chain, scraping_service=svc)

    assert reply == "The EU AI Act entered into force in 2024."
    assert svc.calls == ["eu ai act"]


async def test_search_intent_with_no_results_reports_empty_registry() -> None:
    chain = ScriptedChain(['{"kind": "search", "query": "obscure thing"}'])
    svc = FakeScrapingService([])

    reply = await route("latest on obscure thing", session=None, chain=chain, scraping_service=svc)

    assert "locked site registry" in reply


async def test_question_intent_runs_the_refine_loop() -> None:
    # 1st call: intent -> question; 2nd: draft; 3rd: eval (high score, loop stops)
    chain = ScriptedChain(
        [
            '{"kind": "question", "query": null}',
            "Paris is the capital of France.",
            '{"score": 0.95, "critique": "accurate"}',
        ]
    )

    reply = await route("capital of France?", session=None, chain=chain)

    assert reply == "Paris is the capital of France."
