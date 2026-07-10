"""Standalone scraper — run the acquisition + filtering pipeline from any
machine against the shared database, while the bot itself lives elsewhere
(e.g. Render with RUN_SCRAPER_JOBS=false).

This does NOT conflict with the hosted bot: only getUpdates/webhooks are
exclusive per token; *sending* the admin "N new items — /queue" DM is safe.

Usage (from the repo root, same .env as the bot):
    docker compose run --rm bot python -m app.scraper_cli            # rss only
    docker compose run --rm bot python -m app.scraper_cli webpage
    docker compose run --rm bot python -m app.scraper_cli all

Types: rss, email, webpage, community, telegram, linkedin, all
Special: `hard` = community + linkedin + webpage (the datacenter-blocked set,
meant to be run from a home/residential IP).
"""
import asyncio
import sys

from aiogram import Bot

from app.config import get_settings
from app.logging_setup import get_logger, setup_logging

ALL_TYPES = ["rss", "email", "webpage", "community", "telegram", "linkedin"]


async def main(args: list[str]) -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    log = get_logger("scraper_cli")

    if not args:
        types = ["rss"]
    elif "all" in args:
        types = ALL_TYPES
    elif "hard" in args:
        # sources commonly blocked from datacenter IPs (run from a home IP):
        # Reddit, LinkedIn guest, and Cloudflare-protected web pages.
        types = ["community", "linkedin", "webpage"]
    else:
        invalid = [a for a in args if a not in ALL_TYPES]
        if invalid:
            print(f"Unknown type(s): {', '.join(invalid)}. "
                  f"Valid: {', '.join(ALL_TYPES)}, all")
            return 2
        types = args

    # load /settext overrides + the /setproxy runtime proxy before scraping
    from app.main import load_text_overrides
    await load_text_overrides()

    from app.scheduler.jobs import run_source_types

    bot = Bot(settings.bot_token)
    total = 0
    try:
        for source_type in types:
            log.info("cli_cycle_start", type=source_type)
            total += await run_source_types(bot, [source_type], notify_admins=True)
        log.info("cli_done", types=types, new_pending=total)
        print(f"\nDone: {total} new item(s) queued for review across "
              f"{', '.join(types)}. Review them in the bot: /queue")
    finally:
        await bot.session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
