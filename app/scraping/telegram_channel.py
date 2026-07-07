"""Public Telegram channel scraper — the practical "social media" channel.

Most Armenian companies that post vacancies on FB/IG also run public Telegram
channels, and public channels expose a no-login web preview at
https://t.me/s/<name>. That preview is stable, unauthenticated HTML — unlike
Facebook/Instagram, which require login and actively block scrapers.

Register targets as: /addsource telegram https://t.me/s/companychannel
(plain t.me/<name> URLs and bare @names are normalized automatically).
"""
import re
from datetime import datetime

from bs4 import BeautifulSoup

from app.db.models import Source
from app.logging_setup import get_logger
from app.scraping.base import RawOpportunity, SourceHandler
from app.scraping.community import OPPORTUNITY_PATTERN
from app.scraping.http import polite_get
from app.scraping.webpage import LISTING_KEYWORDS

log = get_logger("scraping.telegram")


def normalize_channel_url(url: str) -> str:
    name = url.strip()
    name = name.removeprefix("https://").removeprefix("http://")
    name = name.removeprefix("t.me/").removeprefix("telegram.me/")
    name = name.removeprefix("s/").lstrip("@").split("/")[0].split("?")[0]
    return f"https://t.me/s/{name}"


def parse_channel_page(html: str, source_id: int) -> list[RawOpportunity]:
    soup = BeautifulSoup(html, "lxml")
    channel_name = None
    header = soup.select_one(".tgme_channel_info_header_title")
    if header:
        channel_name = header.get_text(strip=True)

    results: list[RawOpportunity] = []
    for widget in soup.select(".tgme_widget_message"):
        text_el = widget.select_one(".tgme_widget_message_text")
        if text_el is None:
            continue
        text = text_el.get_text("\n", strip=True)
        blob = text.lower()
        if not (OPPORTUNITY_PATTERN.search(text[:800])
                or any(kw in blob for kw in LISTING_KEYWORDS)):
            continue
        post_ref = widget.get("data-post", "")  # e.g. "channelname/123"
        if not post_ref:
            continue
        url = f"https://t.me/{post_ref}"
        # prefer an external link inside the post as the apply URL
        external = next(
            (a["href"] for a in text_el.find_all("a", href=True)
             if a["href"].startswith("http") and "t.me/" not in a["href"]),
            None,
        )
        time_el = widget.select_one("time[datetime]")
        posted_at = None
        if time_el is not None:
            try:
                posted_at = datetime.fromisoformat(time_el["datetime"])
            except ValueError:
                pass
        title = re.split(r"[\n.!?]", text, 1)[0][:200] or text[:200]
        results.append(RawOpportunity(
            source_id=source_id,
            url=external or url,
            title=title,
            text=text[:5000],
            org=channel_name,
            posted_at=posted_at,
            extra={"tg_post": url},
        ))
    return results


class TelegramChannelScraper(SourceHandler):
    source_type = "telegram"

    async def fetch(self, source: Source) -> list[RawOpportunity]:
        url = normalize_channel_url(source.url)
        resp = await polite_get(url)
        items = parse_channel_page(resp.text, source.id)
        log.info("telegram_fetched", source=source.name, matched=len(items))
        return items
