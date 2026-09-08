from __future__ import annotations

from bot.core.router import route
from bot.llm.base import ChatResult


class ScriptedChain:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)

    async def chat(self, messages, *, temperature=0.7, max_tokens=None) -> ChatResult:
        return ChatResult(text=self._replies.pop(0), provider="fake", model="fake")


class FakeEmailService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def digest(self, instruction: str, session) -> str:
        self.calls.append(instruction)
        return "DIGEST"


async def test_command_is_answered_without_the_model() -> None:
    reply = await route("/start", session=None, chain=ScriptedChain([]))
    assert reply.startswith("Hi.")


async def test_email_intent_dispatches_to_the_email_service() -> None:
    chain = ScriptedChain(['{"kind": "email", "query": "unread today"}'])
    svc = FakeEmailService()

    reply = await route("anything new in my inbox?", session=None, chain=chain, email_service=svc)

    assert reply == "DIGEST"
    assert svc.calls == ["unread today"]


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
