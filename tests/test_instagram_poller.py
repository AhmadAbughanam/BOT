from __future__ import annotations

from bot.channels.instagram.client import DmMessage, DmThread
from bot.channels.instagram.poller import poll_once


class FakeClient:
    self_user_id = "999"  # "me"

    def __init__(self, threads: list[DmThread], messages: dict[str, list[DmMessage]]) -> None:
        self._threads = threads
        self._messages = messages
        self.sent: list[tuple[str, str]] = []

    def inbox_threads(self, amount: int = 20) -> list[DmThread]:
        return self._threads

    def thread_messages(self, thread_id: str, amount: int = 20) -> list[DmMessage]:
        return self._messages.get(thread_id, [])  # newest-first, like instagrapi

    def send_text(self, thread_id: str, text: str) -> None:
        self.sent.append((thread_id, text))


class FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)


def _cursor_store():
    store: dict[tuple[str, str], str] = {}

    def get(_session, channel, key):
        return store.get((channel, key))

    def set_(_session, channel, key, value):
        store[(channel, key)] = value

    return store, get, set_


async def _echo(text: str, _session) -> str:
    return f"re:{text}"


def _msg(mid: str, uid: str, text: str) -> DmMessage:
    return DmMessage(id=mid, thread_id="t1", user_id=uid, text=text)


async def test_processes_new_inbound_messages_and_replies_in_order() -> None:
    client = FakeClient(
        [DmThread(id="t1", user_ids=["7", "999"])],
        {"t1": [_msg("m3", "7", "second"), _msg("m2", "7", "first"), _msg("m1", "999", "mine")]},
    )
    store, get, set_ = _cursor_store()
    session = FakeSession()

    count = await poll_once(
        session, client=client, respond=_echo, cursor_get=get, cursor_set=set_
    )

    assert count == 2
    assert client.sent == [("t1", "re:first"), ("t1", "re:second")]
    assert [m.role for m in session.added] == ["user", "bot", "user", "bot"]
    assert store[("instagram", "t1")] == "m3"


async def test_second_poll_skips_already_seen_messages() -> None:
    client = FakeClient(
        [DmThread(id="t1", user_ids=["7"])],
        {"t1": [_msg("m2", "7", "hi"), _msg("m1", "7", "older")]},
    )
    store, get, set_ = _cursor_store()
    store[("instagram", "t1")] = "m2"

    count = await poll_once(FakeSession(), client=client, respond=_echo, cursor_get=get, cursor_set=set_)

    assert count == 0
    assert client.sent == []


async def test_ignores_own_and_empty_messages() -> None:
    client = FakeClient(
        [DmThread(id="t1", user_ids=["7"])],
        {"t1": [_msg("m2", "7", "   "), _msg("m1", "999", "mine")]},
    )
    _, get, set_ = _cursor_store()

    count = await poll_once(FakeSession(), client=client, respond=_echo, cursor_get=get, cursor_set=set_)

    assert count == 0
    assert client.sent == []


async def test_allowlist_blocks_unknown_sender_but_cursor_advances() -> None:
    client = FakeClient(
        [DmThread(id="t1", user_ids=["7"])],
        {"t1": [_msg("m1", "7", "hello")]},
    )
    store, get, set_ = _cursor_store()

    count = await poll_once(
        FakeSession(), client=client, respond=_echo, allowed_ids={42}, cursor_get=get, cursor_set=set_
    )

    assert count == 0
    assert client.sent == []
    assert store[("instagram", "t1")] == "m1"
