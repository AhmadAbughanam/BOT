from __future__ import annotations

from bot.scraping.extractors import ScrapedResult, dedup_by_url
from bot.scraping.registry import SearchConfig, Site, load_sites, mirror_to_db, sites_for
from bot.scraping.runner import BrowserRunner, PlaywrightRunner, default_runner
from bot.scraping.service import ScrapingService, default_scraping_service

__all__ = [
    "BrowserRunner",
    "PlaywrightRunner",
    "ScrapedResult",
    "ScrapingService",
    "SearchConfig",
    "Site",
    "default_runner",
    "default_scraping_service",
    "dedup_by_url",
    "load_sites",
    "mirror_to_db",
    "sites_for",
]
