from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

from bot.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class DmThread:
    id: str
    user_ids: list[str] = field(default_factory=list)


@dataclass
class DmMessage:
    id: str
    thread_id: str
    user_id: str
    text: str
    timestamp: datetime | None = None


class DirectClient(Protocol):
    @property
    def self_user_id(self) -> str: ...

    def inbox_threads(self, amount: int = 20) -> list[DmThread]: ...

    def thread_messages(self, thread_id: str, amount: int = 20) -> list[DmMessage]: ...

    def send_text(self, thread_id: str, text: str) -> None: ...


class InstagramClient:
    """Adapter over instagrapi. instagrapi is imported lazily and only needed at login."""

    def __init__(self) -> None:
        self._cl = None

    def login(self) -> None:
        try:
            from instagrapi import Client
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                'instagrapi is not installed; run `pip install "bot[instagram]"`'
            ) from exc

        settings = get_settings()
        if not settings.instagram_username or not settings.instagram_password:
            raise RuntimeError("INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD are not set")

        cl = Client()
        session_path = Path(settings.instagram_session_path)
        if session_path.exists():
            cl.load_settings(session_path)
        cl.login(settings.instagram_username, settings.instagram_password)
        cl.dump_settings(session_path)
        self._cl = cl

    @property
    def _client(self):
        if self._cl is None:
            self.login()
        return self._cl

    @property
    def self_user_id(self) -> str:
        return str(self._client.user_id)

    def inbox_threads(self, amount: int = 20) -> list[DmThread]:
        threads = self._client.direct_threads(amount=amount)
        return [DmThread(id=str(t.id), user_ids=[str(u.pk) for u in t.users]) for t in threads]

    def thread_messages(self, thread_id: str, amount: int = 20) -> list[DmMessage]:
        messages = self._client.direct_messages(int(thread_id), amount=amount)
        return [
            DmMessage(
                id=str(m.id),
                thread_id=thread_id,
                user_id=str(m.user_id),
                text=m.text or "",
                timestamp=getattr(m, "timestamp", None),
            )
            for m in messages
        ]

    def send_text(self, thread_id: str, text: str) -> None:
        self._client.direct_send(text, thread_ids=[int(thread_id)])
