from __future__ import annotations

import logging
import sys

from bot.config import get_settings

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    """Set up root logging from settings. Safe to call more than once (`force=True`)."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if settings.log_file:
        handlers.append(logging.FileHandler(settings.log_file, encoding="utf-8"))

    logging.basicConfig(level=level, format=_FORMAT, handlers=handlers, force=True)
