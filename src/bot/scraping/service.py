from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.scraping.extractors import ScrapedResult, dedup_by_url
from bot.scraping.registry import Site, load_sites, sites_for
from bot.scraping.runner import BrowserRunner, default_runner
from bot.storage.models import Item

logger = logging.getLogger(__name__)

_PER_SITE_LIMIT = 5


class ScrapingService:
    def __init__(
        self,
        runner: BrowserRunner | None = None,
        sites: list[Site] | None = None,
    ) -> None:
        self._runner = runner or default_runner()
        self._sites = sites if sites is not None else load_sites()

    async def collect(
        self,
        query: str,
        session: Session,
        *,
        categories: Iterable[str] | None = None,
        subcategories: Iterable[str] | None = None,
        per_site_limit: int = _PER_SITE_LIMIT,
    ) -> list[Item]:
        """Search the matching locked sites for `query`, dedup, and persist new `items`.

        Returns only the rows that were newly inserted.
        """
        targets = sites_for(self._sites, categories, subcategories)
        if not targets:
            logger.info("no registry sites match categories=%s subcategories=%s", categories, subcategories)
            return []

        scraped: list[ScrapedResult] = []
        for site in targets:
            try:
                scraped.extend(await self._runner.search(site, query, per_site_limit))
            except Exception as exc:  # noqa: BLE001 - one bad site must not kill the batch
                logger.warning("scrape failed for %s: %s", site.id, exc)

        return _persist_new(session, dedup_by_url(scraped))


def _persist_new(session: Session, results: list[ScrapedResult]) -> list[Item]:
    if not results:
        return []
    urls = [r.url for r in results]
    known = set(session.execute(select(Item.url).where(Item.url.in_(urls))).scalars())

    new_items: list[Item] = []
    for result in results:
        if result.url in known:
            continue
        known.add(result.url)
        item = Item(
            source_id=result.source_id,
            title=result.title or result.url,
            url=result.url,
            category=result.category,
            subcategory=result.subcategory,
        )
        session.add(item)
        new_items.append(item)
    return new_items
