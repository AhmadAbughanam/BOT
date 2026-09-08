from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

CASES = {
    "deploy/systemd/bot-api.service": ["ExecStart=", "Restart=on-failure", "bot.main:app"],
    "deploy/systemd/bot-task@.service": ["bot.scheduler run %i", "Type=oneshot"],
    "deploy/nginx/bot.conf": ["/telegram/webhook", "proxy_pass", "listen 443 ssl"],
    "deploy/cron/bot.cron": ["bot.scheduler run email-digest", "bot.scheduler run daily-wrap"],
    "deploy/logrotate/bot": ["rotate", "copytruncate"],
    "deploy/deploy.sh": ["alembic upgrade head", "systemctl restart bot-api"],
    "Dockerfile": ["uvicorn", "playwright/python"],
}


@pytest.mark.parametrize("rel_path,needles", CASES.items(), ids=list(CASES))
def test_deploy_asset_present_and_sane(rel_path: str, needles: list[str]) -> None:
    path = ROOT / rel_path
    assert path.is_file(), f"missing {rel_path}"
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{rel_path} missing {needle!r}"


def test_cron_covers_every_timed_task() -> None:
    from bot.scheduler.config import load_tasks

    cron = (ROOT / "deploy/cron/bot.cron").read_text(encoding="utf-8")
    for task in load_tasks():
        if task.get("at"):
            assert f"run {task['name']}" in cron, f"cron missing task {task['name']}"
