from __future__ import annotations

import contextlib
import email
import imaplib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from bot.config import get_settings

logger = logging.getLogger(__name__)

Connect = Callable[[], "imaplib.IMAP4"]

_HEADER_FETCH = "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])"


@dataclass
class ImapCriteria:
    unseen: bool = False
    since: date | None = None
    before: date | None = None
    from_contains: str | None = None
    subject_contains: str | None = None

    def to_imap_string(self) -> str:
        parts: list[str] = []
        if self.unseen:
            parts.append("UNSEEN")
        if self.since:
            parts.append(f"SINCE {self.since:%d-%b-%Y}")
        if self.before:
            parts.append(f"BEFORE {self.before:%d-%b-%Y}")
        if self.from_contains:
            parts.append(f'FROM "{self.from_contains}"')
        if self.subject_contains:
            parts.append(f'SUBJECT "{self.subject_contains}"')
        return f"({' '.join(parts)})" if parts else "ALL"


@dataclass
class MailHeader:
    uid: str
    message_id: str
    from_addr: str
    subject: str
    date: datetime | None

    @property
    def date_str(self) -> str:
        return f"{self.date:%Y-%m-%d %H:%M}" if self.date else "?"


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (ValueError, LookupError):  # pragma: no cover - malformed header
        return value.strip()


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _parse_header_fetch(uid: bytes, msg_data: list) -> MailHeader:
    raw = b""
    for part in msg_data:
        if isinstance(part, tuple) and len(part) == 2:
            raw = part[1]
            break
    msg = email.message_from_bytes(raw)
    return MailHeader(
        uid=uid.decode() if isinstance(uid, bytes) else str(uid),
        message_id=(msg.get("Message-ID") or "").strip(),
        from_addr=_decode(msg.get("From")),
        subject=_decode(msg.get("Subject")),
        date=_parse_date(msg.get("Date")),
    )


def _default_connect() -> imaplib.IMAP4:
    s = get_settings()
    cls = imaplib.IMAP4_SSL if s.email_imap_ssl else imaplib.IMAP4
    conn = cls(s.email_imap_host, s.email_imap_port)
    conn.login(s.email_address, s.email_password)
    return conn


class MailboxReader:
    """Read-only IMAP access. Never sends, moves, or deletes anything."""

    def __init__(self, connect: Connect | None = None) -> None:
        self._connect = connect or _default_connect

    def search(self, criteria: ImapCriteria, mailbox: str = "INBOX", limit: int = 50) -> list[MailHeader]:
        conn = self._connect()
        try:
            conn.select(mailbox, readonly=True)
            typ, data = conn.search(None, criteria.to_imap_string())
            if typ != "OK" or not data or not data[0]:
                return []
            uids = data[0].split()[-limit:]
            headers: list[MailHeader] = []
            for uid in uids:
                typ, msg_data = conn.fetch(uid, _HEADER_FETCH)
                if typ == "OK" and msg_data:
                    headers.append(_parse_header_fetch(uid, msg_data))
            return headers
        finally:
            with contextlib.suppress(Exception):
                conn.logout()
