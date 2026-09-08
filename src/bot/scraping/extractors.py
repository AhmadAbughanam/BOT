from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse


@dataclass
class ScrapedResult:
    title: str
    url: str
    source_id: str
    category: str
    subcategory: str


def clean_title(text: str) -> str:
    return " ".join((text or "").split()).strip()


def absolutize(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _canonical(url: str) -> tuple:
    parsed = urlparse(url)
    return (parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/") or "/", parsed.query)


def dedup_by_url(results: Iterable[ScrapedResult]) -> list[ScrapedResult]:
    """Drop repeats that differ only by trailing slash / fragment, keeping first seen."""
    seen: set[tuple] = set()
    out: list[ScrapedResult] = []
    for result in results:
        key = _canonical(result.url)
        if key in seen:
            continue
        seen.add(key)
        out.append(result)
    return out
