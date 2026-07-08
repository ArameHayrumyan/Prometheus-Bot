"""Application configuration loaded from environment / .env."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram — ONE hardcoded main channel; extra targets via /addchannel.
    # Refs accept "-100123" or "-100123:17" (forum-supergroup topic).
    bot_token: str

    @field_validator("bot_token", mode="after")
    @classmethod
    def _strip_token(cls, v: str) -> str:
        return v.strip()
    channel_id_main: str = ""
    # legacy fallback (pre-unified-channel); other legacy CHANNEL_ID_* env
    # vars are silently ignored via extra="ignore"
    channel_id_undergrad: str = ""
    admin_user_ids: str = ""

    # Database
    database_url: str

    # AI providers
    deepseek_api_key: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""
    groq_rpm: int = 25
    deepseek_rpm: int = 30
    gemini_rpm: int = 12

    # Webhook / polling
    use_webhook: bool = False
    webhook_base_url: str = ""
    webhook_secret: str = "change-me"
    port: int = 8080

    # Newsletter IMAP
    newsletter_imap_host: str = ""
    newsletter_imap_user: str = ""
    newsletter_imap_password: str = ""

    # Scraping
    # false = this instance only serves bot interactions (reminders/digest/
    # expiry still run); scraping is done elsewhere via `python -m app.scraper_cli`
    run_scraper_jobs: bool = True
    scraper_proxy_url: str = ""
    linkedin_proxy_url: str = ""
    linkedin_enabled: bool = True
    playwright_enabled: bool = True

    # Scheduler intervals
    rss_poll_minutes: int = 20
    newsletter_poll_minutes: int = 15
    web_scrape_hours: int = 4
    community_scrape_hours: int = 4
    linkedin_scrape_hours: int = 6

    # Misc
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    log_level: str = "INFO"
    tz: str = "Asia/Yerevan"

    # Strip whitespace from every credential/config string — secrets pasted
    # into GitHub Actions / Render frequently carry a trailing newline, which
    # corrupts auth headers (AI keys), URLs (Gemini) and the DB name.
    @field_validator(
        "deepseek_api_key", "groq_api_key", "gemini_api_key", "webhook_secret",
        "newsletter_imap_host", "newsletter_imap_user", "newsletter_imap_password",
        "scraper_proxy_url", "linkedin_proxy_url", "embedding_model", "tz",
        mode="after",
    )
    @classmethod
    def _strip_str(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("database_url")
    @classmethod
    def _asyncpg_url(cls, v: str) -> str:
        v = v.strip()  # secrets pasted with a trailing newline break the db name
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @property
    def admin_ids(self) -> list[int]:
        return [int(x) for x in self.admin_user_ids.replace(";", ",").split(",") if x.strip()]

    @property
    def main_channel_ref(self) -> str:
        """CHANNEL_ID_MAIN, falling back to the legacy undergrad var so old
        .env files keep working after the unified-channel migration."""
        return (self.channel_id_main or self.channel_id_undergrad).strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
