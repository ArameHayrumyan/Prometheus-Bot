"""LinkedIn guest job-search handler.

Uses the public, no-login jobs-guest HTML endpoint. Deliberately gentle:
one request per registered search per run, long scheduler interval (default
6h), per-domain spacing + jitter from the shared polite client, and a
dedicated optional proxy (LINKEDIN_PROXY_URL) so the egress IP can be changed
with a config edit only. Toggle the whole handler with LINKEDIN_ENABLED.

Note: scraping LinkedIn may violate its ToS even without login; this handler
is intentionally low-volume and fully removable via config. The recommended
primary LinkedIn channel is job-alert emails into the newsletter mailbox,
which flow through EmailNewsletterScraper instead.
"""
import asyncio
import random

from bs4 import BeautifulSoup

from app.config import get_settings
from app.db.models import Source
from app.logging_setup import get_logger
from app.scraping.base import RawOpportunity, SourceHandler
from app.scraping.http import polite_get

log = get_logger("scraping.linkedin")


def parse_guest_jobs(html: str, source_id: int) -> list[RawOpportunity]:
    soup = BeautifulSoup(html, "lxml")
    results: list[RawOpportunity] = []
    for card in soup.select("li"):
        link = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
        title_el = card.select_one(".base-search-card__title, h3")
        if not link or not title_el:
            continue
        title = " ".join(title_el.get_text(" ", strip=True).split())
        url = link.get("href", "").split("?")[0]
        if not url or not title:
            continue
        org_el = card.select_one(".base-search-card__subtitle, h4")
        loc_el = card.select_one(".job-search-card__location")
        org = " ".join(org_el.get_text(" ", strip=True).split()) if org_el else None
        loc = " ".join(loc_el.get_text(" ", strip=True).split()) if loc_el else ""
        results.append(RawOpportunity(
            source_id=source_id, url=url, title=title[:500],
            text=f"{title} at {org or 'unknown company'}. Location: {loc}.",
            org=org, extra={"location": loc},
        ))
    return results


class LinkedInGuestScraper(SourceHandler):
    source_type = "linkedin"

    async def fetch(self, source: Source) -> list[RawOpportunity]:
        settings = get_settings()
        if not settings.linkedin_enabled:
            log.info("linkedin_disabled")
            return []
        # extra jitter on top of domain spacing — never a predictable cadence
        await asyncio.sleep(random.uniform(2, 15))
        proxy = settings.linkedin_proxy_url or settings.scraper_proxy_url or None
        resp = await polite_get(source.url, proxy=proxy, headers={
            "Referer": "https://www.linkedin.com/jobs/search",
        })
        items = parse_guest_jobs(resp.text, source.id)
        log.info("linkedin_fetched", source=source.name, jobs=len(items))
        return items
