from __future__ import annotations

import asyncio
import logging
from typing import Protocol
from urllib.parse import quote_plus

from bot.config import get_settings
from bot.scraping.extractors import (
    ScrapedResult,
    absolutize,
    clean_title,
    is_http_url,
)
from bot.scraping.registry import Site

logger = logging.getLogger(__name__)


class BrowserRunner(Protocol):
    async def search(self, site: Site, query: str, limit: int) -> list[ScrapedResult]: ...


class PlaywrightRunner:
    """Drives a headless Chromium via Playwright. Import is lazy so the rest of the
    package works in environments without the browser installed."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        timeout_ms: int | None = None,
        per_site_delay: float | None = None,
    ) -> None:
        settings = get_settings()
        self._headless = settings.playwright_headless if headless is None else headless
        self._timeout = settings.scrape_timeout_ms if timeout_ms is None else timeout_ms
        self._delay = settings.scrape_per_site_delay if per_site_delay is None else per_site_delay

    async def search(self, site: Site, query: str, limit: int) -> list[ScrapedResult]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "playwright is not installed; run `pip install playwright && playwright install chromium`"
            ) from exc

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._headless)
            page = await browser.new_page()
            try:
                await self._open_results(page, site, query)
                anchors = await page.query_selector_all(site.search.result_selector)
                results: list[ScrapedResult] = []
                for anchor in anchors[:limit]:
                    href = await anchor.get_attribute("href")
                    if not href:
                        continue
                    url = absolutize(site.base_url, href)
                    if not is_http_url(url):
                        continue
                    text = clean_title(await anchor.inner_text())
                    results.append(
                        ScrapedResult(
                            title=text or url,
                            url=url,
                            source_id=site.id,
                            category=site.category,
                            subcategory=site.subcategory,
                        )
                    )
                return results
            finally:
                await browser.close()
                await asyncio.sleep(self._delay)

    async def _open_results(self, page, site: Site, query: str) -> None:
        cfg = site.search
        if cfg.mode == "url_template":
            assert cfg.url_template is not None
            await page.goto(cfg.url_template.format(query=quote_plus(query)), timeout=self._timeout)
            await page.wait_for_load_state("domcontentloaded", timeout=self._timeout)
            return

        await page.goto(site.base_url, timeout=self._timeout)
        if cfg.open_search_selector:
            await page.click(cfg.open_search_selector, timeout=self._timeout)
        await page.fill(cfg.input_selector, query, timeout=self._timeout)
        await page.keyboard.press(cfg.submit_key or "Enter")
        await page.wait_for_load_state("networkidle", timeout=self._timeout)


def default_runner() -> BrowserRunner:
    return PlaywrightRunner()
