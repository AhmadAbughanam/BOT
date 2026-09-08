from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from bot.storage.models import ChannelCursor


def get_cursor(session: Session, channel: str, key: str) -> str | None:
    row = session.get(ChannelCursor, (channel, key))
    return row.value if row is not None else None


def set_cursor(session: Session, channel: str, key: str, value: str) -> None:
    session.execute(
        pg_insert(ChannelCursor)
        .values(channel=channel, key=key, value=value, updated_at=func.now())
        .on_conflict_do_update(
            index_elements=["channel", "key"],
            set_={"value": value, "updated_at": func.now()},
        )
    )
