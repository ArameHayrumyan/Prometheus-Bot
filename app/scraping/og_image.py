"""Fetch a page's social-preview image (og:image / twitter:image).

Used at publish time to attach a real photo to channel posts — more reliable
than Telegram's passive link preview, which many listing pages don't trigger.
"""
import re
from urllib.parse import urljoin

from app.logging_setup import get_logger
from app.scraping.http import polite_get

log = get_logger("scraping.og_image")

# meta tag with property/name before OR after the content attribute
_META_BEFORE = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*["\'](?:og:image(?::url)?|twitter:image(?::src)?)["\']'
    r'[^>]*?content\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_META_AFTER = re.compile(
    r'<meta[^>]+content\s*=\s*["\']([^"\']+)["\'][^>]*?'
    r'(?:property|name)\s*=\s*["\'](?:og:image(?::url)?|twitter:image(?::src)?)["\']',
    re.IGNORECASE)


async def fetch_og_image(url: str) -> str | None:
    """Return an absolute image URL from the page's OpenGraph/Twitter meta,
    or None. Best-effort: short timeout, never raises."""
    if not url or not url.startswith("http"):
        return None
    try:
        resp = await polite_get(url, retries=1, timeout=12)
    except Exception as e:
        log.info("og_fetch_failed", url=url, error=str(e)[:120])
        return None
    html = resp.text[:300000]
    for rx in (_META_BEFORE, _META_AFTER):
        m = rx.search(html)
        if not m:
            continue
        img = m.group(1).strip()
        if img.startswith("//"):
            img = "https:" + img
        elif img.startswith("/"):
            img = urljoin(url, img)
        if img.startswith("http"):
            return img
    return None
