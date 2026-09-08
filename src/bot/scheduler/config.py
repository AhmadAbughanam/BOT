from __future__ import annotations

from bot.yamlconfig import load_app_config


def load_tasks() -> list[dict]:
    return list(load_app_config().get("tasks") or [])


def load_task(name: str) -> dict:
    for task in load_tasks():
        if task.get("name") == name:
            return task
    raise KeyError(f"no scheduled task named {name!r}")
