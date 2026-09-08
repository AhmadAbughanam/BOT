from __future__ import annotations

from pathlib import Path

import yaml

from bot.config import get_settings
from bot.llm.chain import ProviderSpec

_CANDIDATES = ("config/schedule.yaml", "config/schedule.example.yaml")


def _config_path() -> Path | None:
    configured = get_settings().llm_config_path
    if configured:
        return Path(configured)
    for name in _CANDIDATES:
        path = Path(name)
        if path.exists():
            return path
    return None


def _load() -> dict:
    path = _config_path()
    if path is None or not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_chain() -> list[ProviderSpec]:
    entries = ((_load().get("llm") or {}).get("chain")) or []
    return [
        ProviderSpec(
            provider=entry["provider"],
            model=entry["model"],
            rpm=entry.get("rpm"),
            rpd=entry.get("rpd"),
        )
        for entry in entries
    ]


def load_loop_defaults() -> dict:
    return (_load().get("defaults") or {}).get("loop") or {}
