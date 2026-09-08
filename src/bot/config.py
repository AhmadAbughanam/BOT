from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # runtime
    tz: str = "UTC"
    app_env: str = "dev"  # dev | prod
    log_level: str = "info"
    log_file: str = ""  # when set, logs also go to this file (for logrotate)

    # database
    database_url: str = "postgresql+psycopg://bot:bot@localhost:5432/bot"
    embed_dim: int = 768

    # email (read + filter the mailbox; also a delivery target)
    email_imap_host: str = ""
    email_imap_port: int = 993
    email_imap_ssl: bool = True
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_address: str = ""
    email_password: str = ""
    email_brief_to: str = ""

    # telegram
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_webhook_secret: str = ""
    telegram_default_chat_id: str = ""  # where scheduled briefings are delivered

    # llm providers (chain order lives in config/schedule.yaml -> llm.chain)
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    cerebras_api_key: str = ""
    ollama_host: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1:8b"

    # where the llm.chain / defaults.loop config is read from
    llm_config_path: str = ""

    # scraping
    playwright_headless: bool = True
    scrape_timeout_ms: int = 15000
    scrape_per_site_delay: float = 1.0
    scrape_cache_ttl_min: int = 60
    semantic_dedup_threshold: float = 0.08  # cosine distance <= this counts as a duplicate

    @property
    def allowed_user_ids(self) -> set[int]:
        raw = self.telegram_allowed_user_ids.strip()
        if not raw:
            return set()
        return {int(part) for part in raw.split(",") if part.strip()}

    @property
    def default_chat_id(self) -> int | None:
        raw = self.telegram_default_chat_id.strip()
        return int(raw) if raw else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
