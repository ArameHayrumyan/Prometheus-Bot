"""Auto-click subscription-confirmation links in the dedicated mailbox.

Double opt-in newsletters email a "please confirm your subscription" link;
this reads the mailbox, finds those emails, and GETs the confirmation link so
the subscription activates — no manual clicking. It only touches emails that
look like confirmations and only follows links that look like confirmation
links, and marks just those \\Seen so the opportunity scraper ignores them.

Run a few minutes after subscribe_newsletters.py (and again after any manual
signups). Uses NEWSLETTER_IMAP_* from the environment / .env.

Usage:  python scripts/confirm_subscriptions.py
"""
import email
import imaplib
import os
import re
from email.header import decode_header

import httpx

CONFIRM_SUBJECT = re.compile(
    r"confirm|verify|activate|opt.?in|subscription|subscribe|welcome", re.IGNORECASE)
CONFIRM_LINK = re.compile(
    r"confirm|verify|activate|optin|opt-in|subscription|subscribe|token=", re.IGNORECASE)
_HREF = re.compile(r'href=["\'](https?://[^"\']+)["\']', re.IGNORECASE)


def _load_env():
    # minimal .env loader so the script works without extra deps
    if os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _decode(value: str | None) -> str:
    if not value:
        return ""
    out = ""
    for data, charset in decode_header(value):
        out += data.decode(charset or "utf-8", errors="replace") if isinstance(data, bytes) else data
    return out


def _body(msg) -> str:
    parts = msg.walk() if msg.is_multipart() else [msg]
    html, text = "", ""
    for part in parts:
        if part.get_content_type() not in ("text/html", "text/plain"):
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        decoded = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/html":
            html += decoded
        else:
            text += decoded
    return html or text


def main() -> int:
    _load_env()
    host = os.environ.get("NEWSLETTER_IMAP_HOST")
    user = os.environ.get("NEWSLETTER_IMAP_USER")
    pwd = os.environ.get("NEWSLETTER_IMAP_PASSWORD")
    if not (host and user and pwd):
        print("Set NEWSLETTER_IMAP_HOST / _USER / _PASSWORD (in .env).")
        return 2

    conn = imaplib.IMAP4_SSL(host)
    conn.login(user, pwd)
    conn.select("INBOX")
    status, data = conn.search(None, "UNSEEN")
    ids = data[0].split() if status == "OK" else []
    print(f"{len(ids)} unread emails to scan.\n")

    confirmed = 0
    with httpx.Client(timeout=20, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"}) as client:
        for msg_id in ids:
            st, msg_data = conn.fetch(msg_id, "(RFC822)")
            payload = next((p for p in (msg_data or [])
                            if isinstance(p, tuple) and len(p) >= 2), None)
            if st != "OK" or payload is None:
                continue
            msg = email.message_from_bytes(payload[1])
            subject = _decode(msg.get("Subject"))
            sender = _decode(msg.get("From"))
            if not CONFIRM_SUBJECT.search(subject):
                continue
            body = _body(msg)
            links = [u for u in _HREF.findall(body) if CONFIRM_LINK.search(u)]
            if not links:
                continue
            target = links[0]
            try:
                r = client.get(target)
                print(f"✅ confirmed «{subject[:50]}» from {sender[:40]} -> {r.status_code}")
                conn.store(msg_id, "+FLAGS", "\\Seen")
                confirmed += 1
            except Exception as e:
                print(f"⚠️  couldn't open link for «{subject[:50]}»: {str(e)[:60]}")
    conn.logout()
    print(f"\nConfirmed {confirmed} subscription(s). "
          "Opportunity emails will now arrive and be scraped automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
