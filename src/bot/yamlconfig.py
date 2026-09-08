from __future__ import annotations

from pathlib import Path

import yaml

from bot.config import get_settings

_CANDIDATES = ("config/schedule.yaml", "config/schedule.example.yaml")


def load_app_config() -> dict:
    """Read the schedule / llm config file (``config/schedule.yaml``, else the example)."""
    configured = get_settings().llm_config_path
    paths = [Path(configured)] if configured else [Path(name) for name in _CANDIDATES]
    for path in paths:
        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}
