from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from bot.channels.email.service import EmailService
from bot.core.intent import classify_intent
from bot.llm.chain import LLMChain, default_chain
from bot.llm.loader import load_loop_defaults
from bot.refine.loop import RefineConfig, refine
from bot.scraping.service import ScrapingService, default_scraping_service

logger = logging.getLogger(__name__)

COMMANDS: dict[str, str] = {
    "/start": "Hi. Send me a question, ask about your mail, or ask for the latest on a topic.",
    "/help": (
        "Type a question and I'll answer after a self-review pass. "
        'Ask about your inbox ("summarize unread mail, skip newsletters"), '
        'or ask for current news ("latest on the EU AI act"). '
        "Commands: /start, /help."
    ),
}


async def route(
    text: str,
    session: Session,
    *,
    chain: LLMChain | None = None,
    email_service: EmailService | None = None,
    scraping_service: ScrapingService | None = None,
) -> str:
    """Detect intent and dispatch: command, email digest, registry search, or the refine loop."""
    text = text.strip()
    if text.startswith("/"):
        return COMMANDS.get(text.split()[0], "Unknown command. Try /help.")

    chain = chain or default_chain()
    intent = await classify_intent(text, chain)
    logger.info("routed message as %s", intent.kind)

    if intent.kind == "email":
        service = email_service or EmailService(chain=chain)
        if intent.action == "draft_reply":
            return await service.draft_reply(intent.query or text, session)
        return await service.digest(intent.query or text, session)

    cfg = RefineConfig.from_mapping(load_loop_defaults())

    if intent.kind == "search":
        service = scraping_service or default_scraping_service()
        items = await service.collect(intent.query or text, session)
        if not items:
            return "Nothing found in the locked site registry for that."
        context = "\n".join(f"- {it.title} ({it.url})" for it in items)
        result = await refine(text, chain, cfg, context=context, task="search", session=session)
        return result.answer

    result = await refine(text, chain, cfg, task="chat", session=session)
    return result.answer
