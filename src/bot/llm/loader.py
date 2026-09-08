from __future__ import annotations

from bot.llm.chain import ProviderSpec
from bot.llm.embeddings import EmbedSpec
from bot.yamlconfig import load_app_config


def load_chain() -> list[ProviderSpec]:
    entries = ((load_app_config().get("llm") or {}).get("chain")) or []
    return [
        ProviderSpec(
            provider=entry["provider"],
            model=entry["model"],
            rpm=entry.get("rpm"),
            rpd=entry.get("rpd"),
        )
        for entry in entries
    ]


def load_embeddings() -> list[EmbedSpec]:
    entries = ((load_app_config().get("llm") or {}).get("embeddings")) or []
    return [EmbedSpec(provider=entry["provider"], model=entry["model"]) for entry in entries]


def load_loop_defaults() -> dict:
    return (load_app_config().get("defaults") or {}).get("loop") or {}
