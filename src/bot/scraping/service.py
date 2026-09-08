from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.config import get_settings
from bot.llm.embeddings import EmbeddingChain
from bot.scraping.extractors import ScrapedResult, dedup_by_url
from bot.scraping.registry import Site, load_sites, sites_for
from bot.scraping.runner import BrowserRunner, default_runner
from bot.storage.models import Item
from bot.storage.vectors import cosine, embed_and_store, has_semantic_duplicate

logger = logging.getLogger(__name__)

_PER_SITE_LIMIT = 5


class ScrapingService:
    def __init__(
        self,
        runner: BrowserRunner | None = None,
        sites: list[Site] | None = None,
        embedding_chain: EmbeddingChain | None = None,
    ) -> None:
        self._runner = runner or default_runner()
        self._sites = sites if sites is not None else load_sites()
        self._embeddings = embedding_chain
        self._threshold = get_settings().semantic_dedup_threshold

    async def collect(
        self,
        query: str,
        session: Session,
        *,
        categories: Iterable[str] | None = None,
        subcategories: Iterable[str] | None = None,
        per_site_limit: int = _PER_SITE_LIMIT,
    ) -> list[Item]:
        """Search matching sites, drop URL and (if configured) semantic duplicates,
        persist the survivors as `items`, and embed them. Returns the new rows."""
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

        scraped = dedup_by_url(scraped)
        if self._embeddings is not None and scraped:
            try:
                scraped = await self._semantic_filter(session, scraped)
            except Exception as exc:  # noqa: BLE001 - best effort
                logger.warning("semantic dedup skipped: %s", exc)

        new_items = _persist_new(session, scraped)

        if self._embeddings is not None and new_items:
            try:
                session.flush()
                await embed_and_store(session, new_items, self._embeddings)
            except Exception as exc:  # noqa: BLE001 - best effort
                logger.warning("embedding new items failed: %s", exc)

        return new_items

    async def _semantic_filter(
        self, session: Session, scraped: list[ScrapedResult]
    ) -> list[ScrapedResult]:
        result = await self._embeddings.embed([r.title or r.url for r in scraped])
        near = 1.0 - self._threshold
        kept: list[ScrapedResult] = []
        kept_vectors: list[list[float]] = []
        for item, vector in zip(scraped, result.vectors):
            if has_semantic_duplicate(session, vector, self._threshold):
                continue
            if any(cosine(vector, seen) >= near for seen in kept_vectors):
                continue
            kept.append(item)
            kept_vectors.append(vector)
        return kept


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


def default_scraping_service() -> ScrapingService:
    """ScrapingService wired with the configured embedding chain (if any)."""
    from bot.llm.embeddings import default_embedding_chain

    return ScrapingService(embedding_chain=default_embedding_chain())
