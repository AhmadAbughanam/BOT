from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.channels.email.service import EmailService
from bot.channels.telegram.client import TelegramClient
from bot.config import get_settings
from bot.connectors import Connector, get_connector
from bot.core.formatting import for_telegram
from bot.llm.chain import LLMChain, default_chain
from bot.llm.loader import load_loop_defaults
from bot.refine.loop import RefineConfig, refine
from bot.scheduler.config import load_task
from bot.scraping.service import ScrapingService
from bot.storage.models import Brief, Message

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    task: str
    channel: str
    content: str


@dataclass
class TaskDeps:
    chain: LLMChain
    email: EmailService
    scraping: ScrapingService
    connector: Callable[[str], Connector]
    telegram: TelegramClient | None

    @classmethod
    def build(cls) -> "TaskDeps":
        chain = default_chain()
        return cls(
            chain=chain,
            email=EmailService(chain=chain),
            scraping=ScrapingService(),
            connector=get_connector,
            telegram=TelegramClient(),
        )


async def run_task(
    name: str,
    session: Session,
    *,
    deps: TaskDeps | None = None,
    deliver: bool = True,
) -> TaskResult:
    deps = deps or TaskDeps.build()
    task = load_task(name)
    content = await _dispatch(task, deps, session)

    session.add(Brief(task=name, channel="telegram", content=content))
    result = TaskResult(task=name, channel="telegram", content=content)

    if deliver:
        await _deliver(result, deps)
    return result


async def _dispatch(task: dict, deps: TaskDeps, session: Session) -> str:
    source = task.get("source")
    params = dict(task.get("params") or {})

    if source == "email":
        instruction = params.get("filter") or _email_instruction(params)
        return await deps.email.digest(instruction, session)

    if source == "scraping":
        items = await deps.scraping.collect(
            _scrape_query(task, params),
            session,
            categories=params.get("categories"),
            subcategories=params.get("subcategories"),
        )
        return await _brief_from_items(deps, items, session, task["name"])

    if source == "connector":
        connector = deps.connector(task["connector"])
        return await connector.fetch(params)

    if source == "core" and task.get("action") == "recap":
        return _recap(session)

    raise ValueError(f"task {task.get('name')!r}: unsupported source {source!r}")


def _email_instruction(params: dict) -> str:
    bits = []
    if params.get("only_unread"):
        bits.append("unread")
    window = params.get("window_hours")
    if window:
        bits.append(f"from the last {window} hours")
    group = params.get("group_by")
    tail = f", grouped by {group}" if group else ""
    return f"Summarise {' '.join(bits) or 'recent'} mail{tail}."


def _scrape_query(task: dict, params: dict) -> str:
    if params.get("query"):
        return str(params["query"])
    topics = params.get("subcategories") or params.get("categories") or [task["name"]]
    return ", ".join(topics)


async def _brief_from_items(deps: TaskDeps, items, session: Session, task_name: str) -> str:
    if not items:
        return "Nothing new."
    context = "\n".join(f"- {it.title} ({it.url})" for it in items)
    cfg = RefineConfig.from_mapping(load_loop_defaults())
    result = await refine(
        "Summarise the items below as a short briefing, most important first.",
        deps.chain,
        cfg,
        context=context,
        task=task_name,
        session=session,
    )
    return result.answer


def _recap(session: Session) -> str:
    since = datetime.now(UTC) - timedelta(hours=24)
    asked = list(
        session.execute(
            select(Message.text).where(Message.role == "user", Message.created_at >= since)
        ).scalars()
    )
    briefs = list(
        session.execute(select(Brief.task).where(Brief.created_at >= since)).scalars()
    )
    lines = [f"Recap ({len(asked)} question(s) asked, {len(briefs)} brief(s) sent):"]
    lines += [f"· {q}" for q in asked[:10] if q]
    return "\n".join(lines)


async def _deliver(result: TaskResult, deps: TaskDeps) -> None:
    chat_id = get_settings().default_chat_id
    if chat_id is None or deps.telegram is None:
        logger.info("task %s: no default chat id, not delivering", result.task)
        return
    await deps.telegram.send_message(chat_id, for_telegram(result.content))
