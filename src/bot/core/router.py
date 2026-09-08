from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from bot.channels.email.service import EmailService
from bot.core.intent import classify_intent
from bot.llm.chain import LLMChain, default_chain
from bot.llm.loader import load_loop_defaults
from bot.refine.loop import RefineConfig, refine

logger = logging.getLogger(__name__)

COMMANDS: dict[str, str] = {
    "/start": "Hi. Send me a question, or ask me to check your mail.",
    "/help": (
        "Type a question and I'll answer after a self-review pass. "
        "Or ask about your inbox, e.g. \"summarize unread mail from the last day, skip newsletters\". "
        "Commands: /start, /help."
    ),
}


async def route(
    text: str,
    session: Session,
    *,
    chain: LLMChain | None = None,
    email_service: EmailService | None = None,
) -> str:
    """Detect intent and dispatch: command -> canned, email -> digest, question -> refine loop."""
    text = text.strip()
    if text.startswith("/"):
        return COMMANDS.get(text.split()[0], "Unknown command. Try /help.")

    chain = chain or default_chain()
    intent = await classify_intent(text, chain)
    logger.info("routed message as %s", intent.kind)

    if intent.kind == "email":
        service = email_service or EmailService(chain=chain)
        return await service.digest(intent.query or text, session)

    cfg = RefineConfig.from_mapping(load_loop_defaults())
    result = await refine(text, chain, cfg, task="chat", session=session)
    return result.answer
