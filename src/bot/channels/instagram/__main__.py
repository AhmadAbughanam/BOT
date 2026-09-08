"""Instagram DM poller.

    python -m bot.channels.instagram poll               # one pass
    python -m bot.channels.instagram poll --loop        # keep polling every INSTAGRAM_POLL_INTERVAL
    python -m bot.channels.instagram poll --loop --interval 30
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from bot.channels.instagram.client import InstagramClient
from bot.channels.instagram.poller import poll_once
from bot.config import get_settings
from bot.logging_setup import configure_logging
from bot.storage.db import SessionLocal

logger = logging.getLogger("bot.instagram")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bot.channels.instagram")
    sub = parser.add_subparsers(dest="cmd", required=True)
    poll = sub.add_parser("poll", help="process new DMs")
    poll.add_argument("--loop", action="store_true", help="keep polling")
    poll.add_argument("--interval", type=float, default=None, help="seconds between passes")
    return parser.parse_args()


async def _one_pass(client: InstagramClient) -> int:
    session = SessionLocal()
    try:
        count = await poll_once(
            session, client=client, allowed_ids=get_settings().instagram_allowed_ids
        )
        session.commit()
        return count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def _run(args: argparse.Namespace) -> None:
    client = InstagramClient()
    interval = args.interval or get_settings().instagram_poll_interval

    while True:
        try:
            count = await _one_pass(client)
            logger.info("instagram poll: %d repl(y/ies)", count)
        except Exception:  # noqa: BLE001 - keep the loop alive
            logger.exception("instagram poll failed")
        if not args.loop:
            return
        await asyncio.sleep(interval)


def main() -> None:
    configure_logging()
    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
