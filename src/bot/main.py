from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from bot import __version__
from bot.channels.telegram.webhook import handle_update
from bot.config import get_settings
from bot.logging_setup import configure_logging
from bot.storage.db import get_session

configure_logging()
logger = logging.getLogger("bot")

app = FastAPI(title="BOT", version=__version__)


@app.get("/")
def root() -> dict:
    return {"name": "BOT", "version": __version__, "env": get_settings().app_env}


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    db_ok = True
    try:
        session.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - reported, not raised
        db_ok = False
    return {"status": "ok", "db": db_ok}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    session: Session = Depends(get_session),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    secret = get_settings().telegram_webhook_secret
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=403, detail="bad secret token")
    update = await request.json()
    await handle_update(update, session)
    return {"ok": True}
