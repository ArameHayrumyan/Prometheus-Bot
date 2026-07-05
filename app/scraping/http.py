"""Polite shared HTTP client: per-domain spacing, UA rotation, retries with
exponential backoff + jitter, optional proxy (SCRAPER_PROXY_URL — change the
egress IP with zero code edits).
"""
import asyncio
import random
import time
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.logging_setup import get_logger

log = get_logger("scraping.http")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

_MIN_DOMAIN_INTERVAL = 5.0  # seconds between requests to the same domain
_last_hit: dict[str, float] = {}
_domain_locks: dict[str, asyncio.Lock] = {}


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


async def _respect_domain_spacing(url: str) -> None:
    domain = _domain(url)
    lock = _domain_locks.setdefault(domain, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        wait = _last_hit.get(domain, 0.0) + _MIN_DOMAIN_INTERVAL - now
        if wait > 0:
            await asyncio.sleep(wait + random.uniform(0.2, 1.5))
        _last_hit[domain] = time.monotonic()


async def polite_get(url: str, retries: int = 3, timeout: float = 30.0,
                     proxy: str | None = None, headers: dict | None = None) -> httpx.Response:
    settings = get_settings()
    proxy = proxy or (settings.scraper_proxy_url or None)
    merged_headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }
    if headers:
        merged_headers.update(headers)

    backoff = 2.0
    last_exc: Exception | None = None
    for attempt in range(retries):
        await _respect_domain_spacing(url)
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, proxy=proxy
            ) as client:
                resp = await client.get(url, headers=merged_headers)
            if resp.status_code in (429, 503):
                retry_after = float(resp.headers.get("Retry-After", backoff))
                log.warning("scrape_throttled", url=url, status=resp.status_code,
                            wait=retry_after)
                await asyncio.sleep(min(retry_after, 120) + random.uniform(0, 2))
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as e:
            last_exc = e
            log.warning("scrape_retry", url=url, attempt=attempt + 1, error=str(e)[:200])
            await asyncio.sleep(backoff + random.uniform(0, 1))
            backoff *= 2
    raise last_exc if last_exc else RuntimeError(f"failed to fetch {url}")


async def fetch_rendered(url: str) -> str:
    """Render a JS-heavy page with headless Chromium. Falls back to plain GET
    when Playwright is disabled (e.g. 512MB free-tier hosts) or unavailable."""
    settings = get_settings()
    if not settings.playwright_enabled:
        resp = await polite_get(url)
        return resp.text
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        resp = await polite_get(url)
        return resp.text

    await _respect_domain_spacing(url)
    launch_kwargs: dict = {"headless": True}
    if settings.scraper_proxy_url:
        launch_kwargs["proxy"] = {"server": settings.scraper_proxy_url}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**launch_kwargs)
        try:
            page = await browser.new_page(user_agent=random.choice(USER_AGENTS))
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000)  # let client-side lists render
            return await page.content()
        finally:
            await browser.close()
