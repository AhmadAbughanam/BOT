from __future__ import annotations

from datetime import UTC, datetime

from bot.channels.email.reader import MailHeader
from bot.channels.email.service import EmailService
from bot.llm.base import ChatResult


class ReplyChain:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []

    async def chat(self, messages, *, temperature=0.7, max_tokens=None) -> ChatResult:
        self.prompts.append(messages[-1].content)
        return ChatResult(text=self._replies.pop(0), provider="fake", model="fake")


class FakeReader:
    def __init__(self, headers: list[MailHeader], body: str) -> None:
        self._headers = headers
        self._body = body
        self.body_calls: list[str] = []

    def search(self, criteria, mailbox="INBOX", limit=50):
        return self._headers

    def fetch_body(self, uid, mailbox="INBOX", max_chars=4000):
        self.body_calls.append(uid)
        return self._body


class FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    def execute(self, _stmt):  # for _persist upsert
        return None


def _header(uid: str) -> MailHeader:
    return MailHeader(
        uid=uid,
        message_id=f"<{uid}@x>",
        from_addr="boss@example.com",
        subject="Budget review",
        date=datetime(2026, 9, 1, tzinfo=UTC),
    )


async def test_draft_reply_uses_newest_match_and_marks_it_not_sent() -> None:
    reader = FakeReader([_header("10"), _header("11")], body="Can you send the Q3 numbers?")
    chain = ReplyChain(
        ['{"since_days": 7, "unseen": false}', "Sure — attaching the Q3 numbers now."]
    )
    session = FakeSession()

    out = await EmailService(reader=reader, chain=chain).draft_reply(
        "reply to the last email from my boss", session
    )

    assert reader.body_calls == ["11"]  # newest of the matches
    assert "Draft reply to" in out
    assert "not sent" in out
    assert "Sure — attaching the Q3 numbers now." in out
    assert "Can you send the Q3 numbers?" in chain.prompts[-1]  # body given to the model


async def test_draft_reply_with_no_matches() -> None:
    reader = FakeReader([], body="")
    chain = ReplyChain(['{"unseen": true}'])
    out = await EmailService(reader=reader, chain=chain).draft_reply("reply to nobody", FakeSession())
    assert out == "No matching mail to reply to."
