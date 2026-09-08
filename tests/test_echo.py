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


async def test_echo_replies_and_persists_both_sides() -> None:
    client = FakeClient()
    session = FakeSession()
    update = {"message": {"chat": {"id": 42}, "from": {"id": 7}, "text": "hi"}}

    await handle_update(update, session, client)

    assert client.sent == [(42, "echo: hi")]
    assert [m.role for m in session.added] == ["user", "bot"]
    assert session.added[1].text == "echo: hi"


async def test_ignores_updates_without_message() -> None:
    client = FakeClient()
    session = FakeSession()

    await handle_update({"channel_post": {}}, session, client)

    assert client.sent == []
    assert session.added == []
