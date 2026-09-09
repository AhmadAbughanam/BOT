from __future__ import annotations

from datetime import date

from bot.channels.email.reader import ImapCriteria, MailboxReader

_MSG_1 = (
    b"From: Bob Recruiter <bob@example.com>\r\n"
    b"Subject: =?UTF-8?B?SGVsbG8gd29ybGQ=?=\r\n"  # "Hello world"
    b"Date: Mon, 01 Sep 2026 10:00:00 +0000\r\n"
    b"Message-ID: <msg-1@example.com>\r\n\r\n"
)
_MSG_2 = (
    b"From: news@digest.example\r\n"
    b"Subject: Weekly digest\r\n"
    b"Date: Tue, 02 Sep 2026 08:30:00 +0000\r\n"
    b"Message-ID: <msg-2@example.com>\r\n\r\n"
)


class FakeIMAP:
    def __init__(self) -> None:
        self.selected: tuple | None = None
        self.search_arg: str | None = None
        self._store = {b"1": _MSG_1, b"2": _MSG_2}

    def select(self, mailbox, readonly=False):
        self.selected = (mailbox, readonly)
        return ("OK", [b"2"])

    def search(self, charset, criteria):
        self.search_arg = criteria
        return ("OK", [b"1 2"])

    def fetch(self, uid, spec):
        return ("OK", [(uid + b" (BODY[HEADER])", self._store[uid]), b")"])

    def logout(self):
        return ("BYE", [b""])


async def test_search_parses_headers_and_uses_readonly_select() -> None:
    fake = FakeIMAP()
    reader = MailboxReader(connect=lambda: fake)

    headers = reader.search(ImapCriteria(unseen=True, since=date(2026, 8, 25)))

    assert fake.selected == ("INBOX", True)
    assert fake.search_arg == "(UNSEEN SINCE 25-Aug-2026)"
    assert [h.message_id for h in headers] == ["<msg-1@example.com>", "<msg-2@example.com>"]
    assert headers[0].subject == "Hello world"  # MIME-decoded
    assert headers[0].from_addr == "Bob Recruiter <bob@example.com>"
    assert headers[0].date is not None and headers[0].date.year == 2026


async def test_search_returns_empty_when_no_matches() -> None:
    class Empty(FakeIMAP):
        def search(self, charset, criteria):
            return ("OK", [b""])

    headers = MailboxReader(connect=lambda: Empty()).search(ImapCriteria())
    assert headers == []


_MULTIPART = (
    b"From: a@b.com\r\nSubject: Hi\r\n"
    b'Content-Type: multipart/alternative; boundary="X"\r\n\r\n'
    b"--X\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
    b"Hello in plain text.\r\n"
    b"--X\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
    b"<p>Hello in <b>html</b>.</p>\r\n"
    b"--X--\r\n"
)


async def test_fetch_body_prefers_plain_text() -> None:
    class BodyIMAP(FakeIMAP):
        def fetch(self, uid, spec):
            return ("OK", [(uid + b" (BODY[])", _MULTIPART), b")"])

    body = MailboxReader(connect=lambda: BodyIMAP()).fetch_body("1")
    assert body == "Hello in plain text."


async def test_fetch_body_falls_back_to_stripped_html() -> None:
    html_only = (
        b"From: a@b.com\r\nSubject: Hi\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n\r\n"
        b"<div><style>x{}</style><p>Body &nbsp;text</p></div>"
    )

    class BodyIMAP(FakeIMAP):
        def fetch(self, uid, spec):
            return ("OK", [(uid + b" (BODY[])", html_only), b")"])

    body = MailboxReader(connect=lambda: BodyIMAP()).fetch_body("1")
    assert body == "Body text"
