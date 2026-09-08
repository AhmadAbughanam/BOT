from __future__ import annotations

from bot.channels.email.filters import FilterSpec, parse_filter, post_filter
from bot.channels.email.reader import ImapCriteria, MailboxReader, MailHeader
from bot.channels.email.service import EmailService

__all__ = [
    "EmailService",
    "FilterSpec",
    "ImapCriteria",
    "MailHeader",
    "MailboxReader",
    "parse_filter",
    "post_filter",
]
