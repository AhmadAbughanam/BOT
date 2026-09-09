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
_BODY_FETCH = "(BODY.PEEK[])"
_BODY_MAX_CHARS = 4000


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


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;?", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_body(raw: bytes, max_chars: int) -> str:
    msg = email.message_from_bytes(raw)
    plain: str | None = None
    html: str | None = None
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            chunk = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except (LookupError, ValueError):  # pragma: no cover - odd charset
            continue
        if ctype == "text/plain" and plain is None:
            plain = chunk
        elif ctype == "text/html" and html is None:
            html = chunk
    body = plain if plain is not None else (_strip_html(html) if html else "")
    body = body.strip()
    return body[:max_chars] + ("…" if len(body) > max_chars else "")


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

    def fetch_body(self, uid: str, mailbox: str = "INBOX", max_chars: int = _BODY_MAX_CHARS) -> str:
        """Fetch and flatten one message's body to plain text (read-only)."""
        conn = self._connect()
        try:
            conn.select(mailbox, readonly=True)
            typ, msg_data = conn.fetch(uid.encode() if isinstance(uid, str) else uid, _BODY_FETCH)
            if typ != "OK" or not msg_data:
                return ""
            raw = b""
            for part in msg_data:
                if isinstance(part, tuple) and len(part) == 2:
                    raw = part[1]
                    break
            return _extract_body(raw, max_chars)
        finally:
            with contextlib.suppress(Exception):
                conn.logout()
