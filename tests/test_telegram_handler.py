from __future__ import annotations

from bot.channels.telegram.webhook import handle_update


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj: object) -> None:
        self.added.append(obj)


def _update(text: str) -> dict:
    return {"message": {"chat": {"id": 42}, "from": {"id": 7}, "text": text}}


async def test_free_text_goes_through_responder_and_persists_both_sides() -> None:
    client = FakeClient()
    session = FakeSession()

    async def responder(question: str, _session) -> str:
        return f"answer to: {question}"

    await handle_update(_update("what's up"), session, client=client, respond=responder)

    assert client.sent == [(42, "answer to: what's up")]
    assert [m.role for m in session.added] == ["user", "bot"]
    assert session.added[1].text == "answer to: what's up"


async def test_commands_are_answered_without_calling_the_responder() -> None:
    client = FakeClient()
    session = FakeSession()
    called = False

    async def responder(question: str, _session) -> str:
        nonlocal called
        called = True
        return "should not run"

    await handle_update(_update("/help"), session, client=client, respond=responder)

    assert called is False
    assert "Commands" in client.sent[0][1]


async def test_ignores_updates_without_message() -> None:
    client = FakeClient()
    session = FakeSession()

    await handle_update({"channel_post": {}}, session, client=client)

    assert client.sent == []
    assert session.added == []
