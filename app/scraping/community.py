"""Public community boards: subreddit new.json listings and HN "Who is hiring"
threads via the Algolia API. No login, no auth-bypass — public JSON only.
"""
import re
from datetime import datetime, timezone

from app.db.models import Source
from app.logging_setup import get_logger
from app.scraping.base import RawOpportunity, SourceHandler
from app.scraping.http import polite_get

log = get_logger("scraping.community")

# Post-title patterns that look like real opportunities rather than discussion
OPPORTUNITY_PATTERN = re.compile(
    r"\b(hiring|intern(ship)?|phd position|open position|funded|scholarship|"
    r"fellowship|studentship|vacanc|job opening|we'?re looking for|"
    r"research assistant|graduate program|apply now)\b",
    re.IGNORECASE,
)


class CommunityBoardScraper(SourceHandler):
    source_type = "community"

    async def fetch(self, source: Source) -> list[RawOpportunity]:
        if source.meta.get("kind") == "hn":
            return await self._fetch_hn(source)
        return await self._fetch_reddit(source)

    async def _fetch_reddit(self, source: Source) -> list[RawOpportunity]:
        resp = await polite_get(source.url, headers={"User-Agent": "moonin-opportunities-bot/1.0"})
        data = resp.json()
        results: list[RawOpportunity] = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = post.get("title", "")
            selftext = post.get("selftext", "")
            if not OPPORTUNITY_PATTERN.search(f"{title} {selftext[:500]}"):
                continue
            permalink = "https://www.reddit.com" + post.get("permalink", "")
            created = post.get("created_utc")
            results.append(RawOpportunity(
                source_id=source.id,
                url=post.get("url_overridden_by_dest") or permalink,
                title=title[:500],
                text=selftext[:5000] or title,
                org=post.get("subreddit_name_prefixed"),
                posted_at=datetime.fromtimestamp(created, tz=timezone.utc) if created else None,
            ))
        log.info("reddit_fetched", source=source.name, matched=len(results))
        return results

    async def _fetch_hn(self, source: Source) -> list[RawOpportunity]:
        """Find the latest 'Who is hiring' story, then pull matching comments."""
        resp = await polite_get(source.url)
        hits = resp.json().get("hits", [])
        story = next((h for h in hits if "who is hiring" in (h.get("title") or "").lower()), None)
        if story is None:
            return []
        story_id = story["objectID"]
        comments_url = (
            f"https://hn.algolia.com/api/v1/search_by_date?tags=comment,story_{story_id}"
            f"&hitsPerPage=100"
        )
        resp = await polite_get(comments_url)
        results: list[RawOpportunity] = []
        for hit in resp.json().get("hits", []):
            text = re.sub(r"<[^>]+>", " ", hit.get("comment_text") or "")
            text = " ".join(text.split())
            if not OPPORTUNITY_PATTERN.search(text[:600]):
                continue
            if not re.search(r"\b(intern|junior|new grad|graduate|entry.level)\b", text, re.I):
                continue  # only entry-level-relevant comments from hiring threads
            url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
            title = text[:120]
            results.append(RawOpportunity(
                source_id=source.id, url=url, title=title, text=text[:5000],
                org="Hacker News - Who is hiring",
            ))
            if len(results) >= 25:
                break
        log.info("hn_fetched", matched=len(results))
        return results
