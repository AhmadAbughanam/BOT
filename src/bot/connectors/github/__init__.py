from __future__ import annotations

from typing import Any

from bot.connectors.base import ConnectorError, HttpGet, default_get

_API = "https://api.github.com"


class GithubConnector:
    """Latest release per watched repo (keyless, unauthenticated GitHub API)."""

    name = "github"

    def __init__(self, get: HttpGet | None = None) -> None:
        self._get = get or default_get

    async def fetch(self, params: dict[str, Any]) -> str:
        repos = params.get("repos") or []
        if not repos:
            return "No repos configured."

        lines: list[str] = []
        for repo in repos:
            try:
                lines.append(await self._latest_release(repo))
            except ConnectorError as exc:
                lines.append(f"{repo}: {exc}")
        return "Latest releases:\n" + "\n".join(lines)

    async def _latest_release(self, repo: str) -> str:
        resp = await self._get(
            f"{_API}/repos/{repo}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
        )
        if getattr(resp, "status_code", 200) == 404:
            raise ConnectorError("no published release")
        resp.raise_for_status()
        data = resp.json()
        tag = data.get("tag_name") or data.get("name") or "?"
        published = (data.get("published_at") or "")[:10]
        return f"{repo} {tag} ({published})"
