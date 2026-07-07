"""Generic web-page scraper (httpx + BeautifulSoup, Playwright when needs_js).

Strategy: extract link+heading candidates that look like opportunity listings
(keyword-scored anchors and list items), then keep the surrounding text block
as the raw description. This is deliberately generic — per-site precision comes
from the normalization + hard gate + admin queue downstream, so a new page URL
is just a DB row, never new code.
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.db.models import Source
from app.logging_setup import get_logger
from app.scraping.base import RawOpportunity, SourceHandler
from app.scraping.http import fetch_rendered, polite_get

log = get_logger("scraping.webpage")

LISTING_KEYWORDS = (
    "intern", "scholar", "fellow", "phd", "master", "grant", "stipend", "funded",
    "position", "vacan", "job", "traineeship", "studentship", "bootcamp",
    "hackathon", "competition", "program", "apply", "engineer", "developer",
    "data scien", "bioinformat", "research assistant",
    # youth-tier listing vocabulary (olympiad/camp sources)
    "olympiad", "contest", "camp", "summer school", "ctf", "robot",
)

SKIP_URL_PARTS = (
    "login", "signin", "signup", "privacy", "cookie", "terms", "facebook.com",
    "twitter.com", "instagram.com", "youtube.com",
    "linkedin.com/company", "/about", "/contact",
)


def _looks_like_listing(text: str, href: str) -> bool:
    t = f"{text} {href}".lower()
    # scheme/fragment guards checked as prefixes — a legit URL may contain
    # '#section' and must not be dropped by a substring match
    if href.lower().startswith(("javascript:", "mailto:", "tel:", "#")):
        return False
    if any(part in href.lower() for part in SKIP_URL_PARTS):
        return False
    if len(text.strip()) < 12:
        return False
    return any(kw in t for kw in LISTING_KEYWORDS)


def extract_candidates(html: str, base_url: str, source_id: int,
                       max_items: int = 30,
                       selector: str | None = None) -> list[RawOpportunity]:
    """Generic link+context harvesting. When a per-source CSS `selector` is
    set (source meta, via /sourcemeta), extraction is scoped to the matching
    container(s) — precision mode for sites where the generic heuristics
    pick up navigation/sidebar noise."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    if selector:
        anchors: list = []
        for node in soup.select(selector):
            if node.name == "a" and node.has_attr("href"):
                anchors.append(node)
            else:
                anchors.extend(node.find_all("a", href=True))
    else:
        anchors = soup.find_all("a", href=True)

    seen_urls: set[str] = set()
    results: list[RawOpportunity] = []
    for a in anchors:
        title = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(base_url, a["href"])
        if not _looks_like_listing(title, href) or href in seen_urls:
            continue
        seen_urls.add(href)
        # context: closest block-level ancestor's text as the raw description
        container = a.find_parent(["li", "article", "tr", "div", "section"]) or a
        context = " ".join(container.get_text(" ", strip=True).split())[:3000]
        results.append(RawOpportunity(
            source_id=source_id, url=href, title=title[:500], text=context,
        ))
        if len(results) >= max_items:
            break
    return results


class WebPageScraper(SourceHandler):
    source_type = "webpage"

    async def fetch(self, source: Source) -> list[RawOpportunity]:
        if source.needs_js:
            html = await fetch_rendered(source.url)
        else:
            resp = await polite_get(source.url)
            html = resp.text
        items = extract_candidates(html, source.url, source.id,
                                   selector=(source.meta or {}).get("selector"))
        log.info("webpage_fetched", source=source.name, candidates=len(items))
        return items
