from __future__ import annotations

TELEGRAM_MAX = 4096
INSTAGRAM_MAX = 1000


def _trim(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def for_telegram(text: str, limit: int = TELEGRAM_MAX) -> str:
    """Trim a reply to Telegram's per-message limit, keeping whole characters."""
    return _trim(text, limit)


def for_instagram(text: str, limit: int = INSTAGRAM_MAX) -> str:
    """Trim a reply to a safe Instagram DM length."""
    return _trim(text, limit)
