from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from bot.storage.models import Source

logger = logging.getLogger(__name__)

_CANDIDATES = ("config/sites.yaml", "config/sites.example.yaml")
_MODES = {"url_template", "search_bar"}


@dataclass
class SearchConfig:
    mode: str
    result_selector: str
    url_template: str | None = None
    open_search_selector: str | None = None
    input_selector: str | None = None
    submit_key: str = "Enter"


@dataclass
class Site:
    id: str
    name: str
    base_url: str
    category: str
    subcategory: str
    search: SearchConfig

    def as_source_row(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "category": self.category,
            "subcategory": self.subcategory,
            "search_config": asdict(self.search),
        }


def _registry_path() -> Path | None:
    for name in _CANDIDATES:
        path = Path(name)
        if path.exists():
            return path
    return None


def _build_site(raw: dict) -> Site | None:
    try:
        search_raw = raw["search"]
        mode = search_raw["mode"]
        if mode not in _MODES:
            raise ValueError(f"unknown search mode {mode!r}")
        search = SearchConfig(
            mode=mode,
            result_selector=search_raw["result_selector"],
            url_template=search_raw.get("url_template"),
            open_search_selector=search_raw.get("open_search_selector"),
            input_selector=search_raw.get("input_selector"),
            submit_key=search_raw.get("submit_key", "Enter"),
        )
        if mode == "url_template" and not search.url_template:
            raise ValueError("url_template mode needs a url_template")
        if mode == "search_bar" and not search.input_selector:
            raise ValueError("search_bar mode needs an input_selector")
        return Site(
            id=raw["id"],
            name=raw["name"],
            base_url=raw["base_url"],
            category=raw["category"],
            subcategory=raw["subcategory"],
            search=search,
        )
    except (KeyError, ValueError) as exc:
        logger.warning("skipping invalid site entry %r: %s", raw.get("id", raw), exc)
        return None


def load_sites(path: Path | str | None = None) -> list[Site]:
    target = Path(path) if path else _registry_path()
    if target is None or not target.exists():
        logger.warning("no site registry found; scraping registry is empty")
        return []
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    sites = [_build_site(raw) for raw in data.get("sites", [])]
    return [s for s in sites if s is not None]


def sites_for(
    sites: Iterable[Site],
    categories: Iterable[str] | None = None,
    subcategories: Iterable[str] | None = None,
) -> list[Site]:
    cats = {c.lower() for c in categories} if categories else None
    subs = {s.lower() for s in subcategories} if subcategories else None
    out = []
    for site in sites:
        if cats and site.category.lower() not in cats:
            continue
        if subs and site.subcategory.lower() not in subs:
            continue
        out.append(site)
    return out


def mirror_to_db(session: Session, sites: list[Site] | None = None) -> int:
    """Upsert the registry into the `sources` table. Returns the row count."""
    sites = sites if sites is not None else load_sites()
    for site in sites:
        row = site.as_source_row()
        session.execute(
            pg_insert(Source)
            .values(**row)
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    k: row[k]
                    for k in ("name", "base_url", "category", "subcategory", "search_config")
                },
            )
        )
    return len(sites)
