"""Entrypoint: syncs channels from env, starts scheduler, then runs the bot in
long-polling (local/dev) or webhook (prod) mode based on USE_WEBHOOK.
"""
import asyncio

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
    """Load admin text customizations (/settext) into the i18n layer."""
    from app.db.settings_service import get_setting
    from app.i18n import set_overrides

    async with session_scope() as session:
        set_overrides(await get_setting(session, "i18n_overrides") or {})


async def sync_channels() -> None:
    """Upsert the three degree-level channels from env config."""
    settings = get_settings()
    async with session_scope() as session:
        for code, tg_id in settings.channel_map.items():
            row = (await session.execute(
                select(Channel).where(Channel.degree_level_code == code)
            )).scalar_one_or_none()
            if row is None:
                session.add(Channel(degree_level_code=code, tg_channel_id=tg_id))
            else:
                row.tg_channel_id = tg_id
    log.info("channels_synced", channels=settings.channel_map)


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    settings = get_settings()
    if not settings.webhook_base_url:
        raise RuntimeError("USE_WEBHOOK=true requires WEBHOOK_BASE_URL")
    app = web.Application()
    app.router.add_get("/health", health)
    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=settings.webhook_secret,
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(
        url=settings.webhook_base_url.rstrip("/") + WEBHOOK_PATH,
        secret_token=settings.webhook_secret,
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
