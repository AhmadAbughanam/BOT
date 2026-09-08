from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # runtime
    tz: str = "UTC"
    log_level: str = "info"

    # database
    database_url: str = "postgresql+psycopg://bot:bot@localhost:5432/bot"
    embed_dim: int = 768

    # telegram
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_webhook_secret: str = ""

    @property
    def allowed_user_ids(self) -> set[int]:
        raw = self.telegram_allowed_user_ids.strip()
        if not raw:
            return set()
        return {int(part) for part in raw.split(",") if part.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
