"""Best-effort auto-subscribe the dedicated mailbox to opportunity newsletters.

Fills the email signup form on a curated list of sites via Playwright. Sites
with double opt-in send a confirmation email — run confirm_subscriptions.py a
few minutes later to auto-click those.

Signup forms vary wildly (captchas, iframes, exotic markup), so expect ~half
to succeed; the rest, subscribe by hand from the printed list. This is a
one-time setup, not part of the running system.

Usage (from repo root, .env loaded or NEWSLETTER_IMAP_USER exported):
    python scripts/subscribe_newsletters.py [email]
"""
import asyncio
import os
import sys

# Curated opportunity/fellowship digests worth subscribing the mailbox to.
NEWSLETTERS = [
    "https://www.profellow.com/",
    "https://opportunitydesk.org/",
    "https://www.opportunitiesforafricans.com/",
    "https://opportunitiesforyouth.org/",
    "https://www.youthop.com/",
    "https://www.scholars4dev.com/",
    "https://scholarship-positions.com/",
    "https://www.mladiinfo.eu/",
    "https://bioinformatics.ca/",
    "https://www.findaphd.com/",   # account/alerts
]

COOKIE_WORDS = ("accept", "agree", "got it", "ok", "allow")


async def _dismiss_cookies(page):
    for word in COOKIE_WORDS:
        try:
            btn = page.get_by_role("button", name=lambda n: n and word in n.lower())
            if await btn.count():
                await btn.first.click(timeout=1500)
                return
        except Exception:
            pass


async def subscribe(page, url: str, email: str) -> str:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)
        await _dismiss_cookies(page)
        inp = (await page.query_selector("input[type='email']")
               or await page.query_selector("input[name*='email' i]")
               or await page.query_selector("input[id*='email' i]")
               or await page.query_selector("input[placeholder*='email' i]"))
        if inp is None:
            return f"⚠️  no email field — subscribe by hand: {url}"
        await inp.scroll_into_view_if_needed()
        await inp.fill(email)
        await inp.press("Enter")
        await page.wait_for_timeout(2500)
        return f"✅ submitted: {url}"
    except Exception as e:
        return f"❌ failed ({str(e)[:60]}): {url}"


async def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("NEWSLETTER_IMAP_USER", "")
    if not email:
        print("Provide an email arg or set NEWSLETTER_IMAP_USER.")
        return 2
    print(f"Subscribing {email} to {len(NEWSLETTERS)} newsletters…\n")
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Run: playwright install chromium")
        return 2
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        for url in NEWSLETTERS:
            page = await browser.new_page()
            print(await subscribe(page, url, email))
            await page.close()
        await browser.close()
    print("\nDone. Wait ~5 min, then: python scripts/confirm_subscriptions.py")
    print("Subscribe the ⚠️/❌ ones by hand (open the URL, find the email box).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
