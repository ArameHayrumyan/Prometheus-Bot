"""Bot + Dispatcher assembly: middlewares, routers, command menus."""
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (BotCommand, BotCommandScopeChat,
                           BotCommandScopeDefault)

from app.bot.handlers import analyze, documents, forward, search, start
from app.bot.handlers.admin import ai_admin, queue, sources, taxonomy
from app.bot.middlewares import DbSessionMiddleware, UserMiddleware
from app.config import get_settings
from app.logging_setup import get_logger

log = get_logger("bot.setup")

STUDENT_COMMANDS = [
    BotCommand(command="search", description="🔍 Browse opportunities"),
    BotCommand(command="filters", description="💾 Saved filters & notifications"),
    BotCommand(command="mydocs", description="📎 My resume & documents"),
    BotCommand(command="profile", description="👤 My profile"),
    BotCommand(command="language", description="🌐 Language / Լեզու"),
    BotCommand(command="help", description="ℹ️ Help"),
]

ADMIN_COMMANDS = STUDENT_COMMANDS + [
    BotCommand(command="queue", description="📥 Review queue"),
    BotCommand(command="discards", description="🗑 Discard log"),
    BotCommand(command="stats", description="📊 Pipeline stats"),
    BotCommand(command="listsources", description="🗂 Source registry"),
    BotCommand(command="addsource", description="➕ Add source"),
    BotCommand(command="listfields", description="🔬 Field taxonomy"),
    BotCommand(command="ai_status", description="🤖 AI router status"),
]


def create_bot() -> Bot:
    return Bot(
        token=get_settings().bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(DbSessionMiddleware())
        observer.outer_middleware(UserMiddleware())

    # admin routers first (guarded by IsAdmin filter), then student flows;
    # forward-matching last so commands/FSM take precedence
    dp.include_router(queue.router)
    dp.include_router(sources.router)
    dp.include_router(ai_admin.router)
    dp.include_router(taxonomy.router)
    dp.include_router(start.router)
    dp.include_router(documents.router)
    dp.include_router(search.router)
    dp.include_router(analyze.router)
    dp.include_router(forward.router)
    return dp


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(STUDENT_COMMANDS, scope=BotCommandScopeDefault())
    for admin_id in get_settings().admin_ids:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            log.warning("admin_commands_failed", admin=admin_id, error=str(e)[:150])
