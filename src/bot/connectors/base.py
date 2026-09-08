from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx

HttpGet = Callable[..., Awaitable[Any]]


class ConnectorError(Exception):
    """A connector could not produce a result."""


async def default_get(url: str, *, params: dict | None = None, headers: dict | None = None):
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        return await client.get(url, params=params, headers=headers)


class Connector(Protocol):
    name: str

    async def fetch(self, params: dict[str, Any]) -> str: ...
