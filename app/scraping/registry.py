"""Source registry: maps DB source rows to their typed handlers."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source
from app.logging_setup import get_logger
from app.scraping.base import RawOpportunity, SourceHandler
from app.scraping.community import CommunityBoardScraper
from app.scraping.email_newsletter import EmailNewsletterScraper
from app.scraping.linkedin import LinkedInGuestScraper
from app.scraping.rss import RSSFeedScraper
from app.scraping.webpage import WebPageScraper

log = get_logger("scraping.registry")

HANDLERS: dict[str, SourceHandler] = {
    h.source_type: h
    for h in (
        WebPageScraper(),
        RSSFeedScraper(),
        EmailNewsletterScraper(),
        CommunityBoardScraper(),
        LinkedInGuestScraper(),
    )
}


async def active_sources(session: AsyncSession, source_types: list[str]) -> list[Source]:
    stmt = select(Source).where(Source.active.is_(True), Source.source_type.in_(source_types))
    return list((await session.execute(stmt)).scalars().all())


async def fetch_source(session: AsyncSession, source: Source) -> list[RawOpportunity]:
    handler = HANDLERS.get(source.source_type)
    if handler is None:
        log.warning("no_handler", source_type=source.source_type, source=source.name)
        return []
    try:
        items = await handler.fetch(source)
    except Exception as e:
        # repr(): str() of httpx timeout errors is often empty
        log.warning("source_fetch_failed", source=source.name, error=repr(e)[:300])
        return []
    source.last_checked_at = datetime.now(timezone.utc)
    return items
