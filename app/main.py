"""Entrypoint: syncs channels from env, starts scheduler, then runs the bot in
long-polling (local/dev) or webhook (prod) mode based on USE_WEBHOOK.
"""
import asyncio
import re

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from sqlalchemy import select

from app.bot.setup import create_bot, create_dispatcher, set_bot_commands
from app.config import get_settings
from app.db.base import session_scope
from app.db.models import Channel
from app.logging_setup import get_logger, setup_logging
from app.scheduler.jobs import setup_scheduler

log = get_logger("main")

WEBHOOK_PATH = "/webhook"


async def load_text_overrides() -> None:
    """Load admin text customizations (/settext) and the runtime proxy."""
    from app.db.settings_service import get_setting
    from app.i18n import set_overrides
    from app.scraping.http import set_runtime_proxy

    async with session_scope() as session:
        set_overrides(await get_setting(session, "i18n_overrides") or {})
        set_runtime_proxy(await get_setting(session, "scraper_proxy") or None)


async def sync_channels() -> None:
    """Upsert the single MAIN channel from env (unified-channel model) and
    remove legacy per-degree / youth rows from older versions. Free channels
    (/addchannel) are untouched. Refs accept '-100123' or '-100123:17'."""
    from app.constants import parse_channel_ref

    settings = get_settings()
    ref = settings.main_channel_ref
    if not ref:
        raise RuntimeError("CHANNEL_ID_MAIN is required (the unified channel)")
    chat_id, thread_id = parse_channel_ref(ref)
    async with session_scope() as session:
        rows = (await session.execute(select(Channel))).scalars().all()
        main = next((c for c in rows if c.audience == "main"), None)
        for c in rows:
            # legacy: degree-linked rows and the old youth row
            if c.degree_level_code is not None or c.audience == "youth":
                await session.delete(c)
        if main is None:
            session.add(Channel(tg_channel_id=chat_id, thread_id=thread_id,
                                name="Main", audience="main",
                                degree_level_code=None))
        else:
            main.tg_channel_id = chat_id
            main.thread_id = thread_id
    log.info("channels_synced", main=ref)


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def _safe_webhook_secret(raw: str) -> str:
    """Telegram's secret_token allows only A-Z a-z 0-9 _ - (1-256 chars).
    Render's generateValue can include other characters — strip them."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", raw or "")
    return cleaned or "moonin_webhook_secret"


async def _start_health_server(port: int) -> web.AppRunner:
    """Bind a minimal /health server so Render's web service detects an open
    port. Required in BOTH modes — polling has no server of its own, and the
    cron-job.org keep-alive ping hits /health regardless of mode."""
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=port).start()
    log.info("health_server_started", port=port)
    return runner


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    settings = get_settings()
    if not settings.webhook_base_url:
        raise RuntimeError("USE_WEBHOOK=true requires WEBHOOK_BASE_URL")
    secret = _safe_webhook_secret(settings.webhook_secret)
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/", health)
    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=secret,
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(
        url=settings.webhook_base_url.rstrip("/") + WEBHOOK_PATH,
        secret_token=secret,
        drop_pending_updates=False,
        allowed_updates=dp.resolve_used_update_types(),
    )
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.port)
    await site.start()
    log.info("webhook_started", port=settings.port,
             url=settings.webhook_base_url.rstrip("/") + WEBHOOK_PATH)
    await asyncio.Event().wait()  # run forever


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    # Health server first, so a web host (Render) sees an open port even
    # though polling itself binds nothing.
    await _start_health_server(get_settings().port)
    await bot.delete_webhook(drop_pending_updates=False)
    log.info("polling_started")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("starting", webhook=settings.use_webhook)

    await sync_channels()
    await load_text_overrides()
    bot = create_bot()
    dp = create_dispatcher()
    await set_bot_commands(bot)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    log.info("scheduler_started", jobs=[j.id for j in scheduler.get_jobs()])

    try:
        if settings.use_webhook:
            await run_webhook(bot, dp)
        else:
            await run_polling(bot, dp)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
