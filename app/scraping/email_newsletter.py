"""IMAP newsletter ingestion — a distinct acquisition channel from web scraping.

A dedicated mailbox (env: NEWSLETTER_IMAP_*) is subscribed to opportunity
digests (ProFellow, Opportunity Desk, university career centers, LinkedIn job
alerts...). Unseen messages are parsed, opportunity-looking links + their
surrounding text become RawOpportunity items, and the message is marked seen.

imaplib is synchronous, so all IMAP work runs in a thread.
"""
import asyncio
import email
import imaplib
from email.header import decode_header
from email.message import Message
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.config import get_settings
from app.db.models import Source
from app.logging_setup import get_logger
from app.scraping.base import RawOpportunity, SourceHandler
from app.scraping.webpage import LISTING_KEYWORDS, SKIP_URL_PARTS

log = get_logger("scraping.email")

# Redirect/tracking domains whose links we keep (the redirect target is the listing)
_MAX_EMAILS_PER_RUN = 20
_MAX_LINKS_PER_EMAIL = 25


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = ""
    for data, charset in parts:
        if isinstance(data, bytes):
            out += data.decode(charset or "utf-8", errors="replace")
        else:
            out += data
    return out


def _best_body(msg: Message) -> tuple[str, bool]:
    """Return (body, is_html), preferring HTML parts."""
    html, text = "", ""
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if ctype not in ("text/html", "text/plain"):
            continue
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            decoded = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if ctype == "text/html":
            html += decoded
        else:
            text += decoded
    return (html, True) if html else (text, False)


def extract_email_opportunities(subject: str, body: str, is_html: bool,
                                source_id: int) -> list[RawOpportunity]:
    results: list[RawOpportunity] = []
    seen: set[str] = set()
    if is_html:
        soup = BeautifulSoup(body, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = " ".join(a.get_text(" ", strip=True).split())
            if not href.startswith("http") or href in seen:
                continue
            if any(part in href.lower() for part in SKIP_URL_PARTS):
                continue
            blob = f"{title} {href}".lower()
            if len(title) < 12 or not any(kw in blob for kw in LISTING_KEYWORDS):
                continue
            seen.add(href)
            container = a.find_parent(["td", "li", "p", "div", "table"]) or a
            context = " ".join(container.get_text(" ", strip=True).split())[:3000]
            # embed the container's other links into the text so the AI TL;DR
            # (which replaces the description) can't drop them — visible text
            # doesn't carry hrefs, so without this email links are lost
            extra = [
                x["href"] for x in container.find_all("a", href=True)
                if x.get("href", "").startswith("http")
                and x["href"] != href
                and not any(p in x["href"].lower() for p in SKIP_URL_PARTS)
            ][:4]
            link_line = ("\nLinks: " + " ".join(dict.fromkeys(extra))) if extra else ""
            results.append(RawOpportunity(
                source_id=source_id, url=href, title=title[:500],
                text=f"[newsletter: {subject}] {context}{link_line}",
                org=urlparse(href).netloc,
            ))
            if len(results) >= _MAX_LINKS_PER_EMAIL:
                break
    else:
        # plain-text digests: line-based, keep lines with a URL + keyword
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if "http" not in line:
                continue
            url = next((w for w in line.split() if w.startswith("http")), None)
            if url:
                url = url.rstrip(".,;:)]>\"'")  # strip trailing prose punctuation
            if not url or url in seen:
                continue
            context = " ".join(lines[max(0, i - 2): i + 3]).strip()
            if not any(kw in context.lower() for kw in LISTING_KEYWORDS):
                continue
            seen.add(url)
            title = context[:120] or subject
            results.append(RawOpportunity(
                source_id=source_id, url=url, title=title,
                text=f"[newsletter: {subject}] {context[:3000]}",
            ))
            if len(results) >= _MAX_LINKS_PER_EMAIL:
                break
    return results


def _fetch_unseen_sync(source_id: int) -> list[RawOpportunity]:
    s = get_settings()
    results: list[RawOpportunity] = []
    conn = imaplib.IMAP4_SSL(s.newsletter_imap_host)
    try:
        conn.login(s.newsletter_imap_user, s.newsletter_imap_password)
        conn.select("INBOX")
        status, data = conn.search(None, "UNSEEN")
        if status != "OK":
            return []
        ids = data[0].split()[:_MAX_EMAILS_PER_RUN]
        for msg_id in ids:
            status, msg_data = conn.fetch(msg_id, "(RFC822)")
            # servers interleave tuples with bare b')' markers — take the tuple
            payload = next((p for p in (msg_data or [])
                            if isinstance(p, tuple) and len(p) >= 2), None)
            if status != "OK" or payload is None:
                continue
            msg = email.message_from_bytes(payload[1])
            subject = _decode(msg.get("Subject"))
            body, is_html = _best_body(msg)
            found = extract_email_opportunities(subject, body, is_html, source_id)
            results.extend(found)
            conn.store(msg_id, "+FLAGS", "\\Seen")
    finally:
        try:
            conn.logout()
        except Exception:
            pass
    return results


class EmailNewsletterScraper(SourceHandler):
    source_type = "email"

    async def fetch(self, source: Source) -> list[RawOpportunity]:
        s = get_settings()
        if not (s.newsletter_imap_host and s.newsletter_imap_user and s.newsletter_imap_password):
            log.info("email_skipped_not_configured")
            return []
        items = await asyncio.to_thread(_fetch_unseen_sync, source.id)
        log.info("email_fetched", items=len(items))
        return items
