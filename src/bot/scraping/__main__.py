"""One-off scrape / registry sync / embedding backfill.

    python -m bot.scraping "openai" --categories tech,news
    python -m bot.scraping --mirror
    python -m bot.scraping --embed-backfill
"""
from __future__ import annotations

import argparse
import asyncio

from bot.logging_setup import configure_logging
from bot.scraping.registry import load_sites, mirror_to_db
from bot.scraping.service import ScrapingService
from bot.storage.db import SessionLocal


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bot.scraping")
    parser.add_argument("query", nargs="?", help="search text")
    parser.add_argument("--categories", default="", help="comma-separated category filter")
    parser.add_argument("--subcategories", default="", help="comma-separated subcategory filter")
    parser.add_argument("--mirror", action="store_true", help="sync config/sites.yaml into the sources table and exit")
    parser.add_argument("--embed-backfill", action="store_true", help="embed all items with no embedding and exit")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    session = SessionLocal()
    try:
        if args.mirror:
            count = mirror_to_db(session)
            session.commit()
            print(f"mirrored {count} site(s) into sources")
            return

        if args.embed_backfill:
            from bot.llm.embeddings import default_embedding_chain
            from bot.storage.vectors import backfill_embeddings

            chain = default_embedding_chain()
            if chain is None:
                raise SystemExit("no llm.embeddings configured in config/schedule.yaml")
            count = await backfill_embeddings(session, chain)
            session.commit()
            print(f"embedded {count} item(s)")
            return

        if not args.query:
            raise SystemExit("a query is required unless --mirror / --embed-backfill is given")

        service = ScrapingService(sites=load_sites())
        items = await service.collect(
            args.query,
            session,
            categories=[c for c in args.categories.split(",") if c] or None,
            subcategories=[s for s in args.subcategories.split(",") if s] or None,
        )
        session.commit()
        print(f"{len(items)} new item(s):")
        for item in items:
            print(f"  [{item.category}/{item.subcategory}] {item.title} - {item.url}")
    finally:
        session.close()


if __name__ == "__main__":
    configure_logging()
    asyncio.run(_run(_parse_args()))
