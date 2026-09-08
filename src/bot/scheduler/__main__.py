"""Scheduled task runner.

    python -m bot.scheduler list
    python -m bot.scheduler run <task> [--no-deliver]
    python -m bot.scheduler crontab [--python PATH] [--workdir DIR]
"""
from __future__ import annotations

import argparse
import asyncio

from bot.logging_setup import configure_logging
from bot.scheduler.config import load_tasks
from bot.scheduler.crontab import crontab_lines
from bot.scheduler.tasks import run_task
from bot.storage.db import SessionLocal


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bot.scheduler")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list configured tasks")

    run = sub.add_parser("run", help="run one task now")
    run.add_argument("task")
    run.add_argument("--no-deliver", action="store_true", help="do not send to Telegram")

    cron = sub.add_parser("crontab", help="print crontab lines for all timed tasks")
    cron.add_argument("--python", default=None)
    cron.add_argument("--workdir", default=None)

    return parser.parse_args()


async def _run_one(task: str, deliver: bool) -> None:
    session = SessionLocal()
    try:
        result = await run_task(task, session, deliver=deliver)
        session.commit()
        print(result.content)
    finally:
        session.close()


def main() -> None:
    configure_logging()
    args = _parse_args()

    if args.cmd == "list":
        for task in load_tasks():
            print(f"{task.get('at', '  -  '):>5}  {task['name']}  (source={task.get('source')})")
    elif args.cmd == "crontab":
        for line in crontab_lines(args.python, args.workdir):
            print(line)
    elif args.cmd == "run":
        asyncio.run(_run_one(args.task, deliver=not args.no_deliver))


if __name__ == "__main__":
    main()
