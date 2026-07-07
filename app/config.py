"""Application configuration loaded from environment / .env."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram — ONE hardcoded main channel; extra targets via /addchannel.
    # Refs accept "-100123" or "-100123:17" (forum-supergroup topic).
    bot_token: str
    channel_id_main: str = ""
    # legacy vars (pre-unified-channel) — used as fallback for CHANNEL_ID_MAIN
    channel_id_undergrad: str = ""
    channel_id_masters: str = ""
    channel_id_phd: str = ""
    channel_id_youth: str = ""
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

    @field_validator("database_url")
    @classmethod
    def _asyncpg_url(cls, v: str) -> str:
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
