from __future__ import annotations

from typing import Any

import feedparser

from bot.connectors.base import HttpGet, default_get


class FeedsConnector:
    """Pulls recent entries from a list of RSS/Atom feed URLs."""

    name = "feeds"

    def __init__(self, get: HttpGet | None = None) -> None:
        self._get = get or default_get

    async def fetch(self, params: dict[str, Any]) -> str:
        urls = params.get("feeds") or []
        max_items = int(params.get("max_items", 10))
        if not urls:
            return "No feeds configured."

        entries: list[tuple[str, str]] = []
        for url in urls:
            try:
                resp = await self._get(url)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.text)
            except Exception:  # noqa: BLE001 - a dead feed must not break the batch
                continue
            for entry in parsed.entries[:max_items]:
                title = (entry.get("title") or "").strip()
                link = (entry.get("link") or "").strip()
                if title:
                    entries.append((title, link))

        if not entries:
            return "No feed items."
        return "\n".join(f"- {title} ({link})" for title, link in entries[:max_items])
