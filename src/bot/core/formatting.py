from __future__ import annotations

TELEGRAM_MAX = 4096


def for_telegram(text: str, limit: int = TELEGRAM_MAX) -> str:
    """Trim a reply to Telegram's per-message limit, keeping whole characters."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
