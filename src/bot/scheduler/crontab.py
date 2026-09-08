from __future__ import annotations

import sys
from pathlib import Path

from bot.scheduler.config import load_tasks


def crontab_lines(python: str | None = None, workdir: str | None = None) -> list[str]:
    """Render one crontab line per task that has an `at: "HH:MM"` time."""
    python = python or sys.executable
    workdir = workdir or str(Path.cwd())
    lines: list[str] = []
    for task in load_tasks():
        at = task.get("at")
        name = task.get("name")
        if not at or not name:
            continue
        hour, minute = at.split(":")
        lines.append(
            f"{int(minute)} {int(hour)} * * * cd {workdir} && {python} -m bot.scheduler run {name}"
        )
    return lines
