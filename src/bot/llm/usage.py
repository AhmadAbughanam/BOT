from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from bot.storage.models import LlmUsage


def _today() -> date:
    return datetime.now(UTC).date()


def record_usage(
    session: Session,
    provider: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    day: date | None = None,
) -> None:
    """Increment the per-provider/model/day counters (upsert)."""
    day = day or _today()
    stmt = (
        pg_insert(LlmUsage)
        .values(
            provider=provider,
            model=model,
            day=day,
            requests=1,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        .on_conflict_do_update(
            constraint="uq_llm_usage_provider_model_day",
            set_={
                "requests": LlmUsage.requests + 1,
                "tokens_in": LlmUsage.tokens_in + tokens_in,
                "tokens_out": LlmUsage.tokens_out + tokens_out,
            },
        )
    )
    session.execute(stmt)


def requests_today(session: Session, provider: str, model: str, day: date | None = None) -> int:
    day = day or _today()
    value = session.execute(
        select(LlmUsage.requests).where(
            LlmUsage.provider == provider,
            LlmUsage.model == model,
            LlmUsage.day == day,
        )
    ).scalar_one_or_none()
    return value or 0
