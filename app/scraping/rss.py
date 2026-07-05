"""RSS/Atom feed handler (feedparser). Cheap to poll, so scheduled frequently."""
import asyncio
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup

from app.db.models import Source
from app.logging_setup import get_logger
from app.scraping.base import RawOpportunity, SourceHandler
from app.scraping.http import polite_get

log = get_logger("scraping.rss")


def _entry_time(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def _strip_html(html: str) -> str:
    return " ".join(BeautifulSoup(html or "", "lxml").get_text(" ", strip=True).split())


class RSSFeedScraper(SourceHandler):
    source_type = "rss"

    async def fetch(self, source: Source) -> list[RawOpportunity]:
        resp = await polite_get(source.url)
        feed = await asyncio.to_thread(feedparser.parse, resp.content)
        results: list[RawOpportunity] = []
        for entry in feed.entries[:50]:
            link = getattr(entry, "link", "") or ""
            title = _strip_html(getattr(entry, "title", ""))
            if not link or not title:
                continue
            summary = _strip_html(getattr(entry, "summary", ""))
            content_list = getattr(entry, "content", None)
            if content_list:
                summary = max([summary] + [_strip_html(c.get("value", "")) for c in content_list],
                              key=len)
            results.append(RawOpportunity(
                source_id=source.id, url=link, title=title[:500],
                text=summary[:5000], posted_at=_entry_time(entry),
            ))
        log.info("rss_fetched", source=source.name, entries=len(results))
        return results
