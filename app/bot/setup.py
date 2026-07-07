"""Bot + Dispatcher assembly: middlewares, routers, command menus."""
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (BotCommand, BotCommandScopeChat,
                           BotCommandScopeDefault)

from app.bot.handlers import analyze, documents, forward, saved, search, start
from app.bot.handlers.admin import (ai_admin, channels, help as admin_help,
                                    queue, sources, taxonomy, texts)
from app.bot.middlewares import DbSessionMiddleware, UserMiddleware
from app.config import get_settings
from app.logging_setup import get_logger

log = get_logger("bot.setup")

# Student menu descriptions are i18n keys (cmd_*): the menu is localized per
# Telegram client language and editable via /settext + /refreshcommands.
STUDENT_COMMAND_KEYS = [
    ("search", "cmd_search"),
    ("saved", "cmd_saved"),
    ("filters", "cmd_filters"),
    ("mydocs", "cmd_mydocs"),
    ("profile", "cmd_profile"),
    ("language", "cmd_language"),
    ("help", "cmd_help"),
]


def student_commands(lang: str) -> list[BotCommand]:
    from app.i18n import t

    return [BotCommand(command=cmd, description=t(key, lang)[:256])
            for cmd, key in STUDENT_COMMAND_KEYS]


ADMIN_EXTRA_COMMANDS = [
    BotCommand(command="adminhelp", description="🛠 Admin reference & examples"),
    BotCommand(command="queue", description="📥 Review queue"),
    BotCommand(command="archive", description="🗂 Shelved for later"),
    BotCommand(command="discards", description="🗑 Discard log"),
    BotCommand(command="stats", description="📊 Pipeline stats"),
    BotCommand(command="digest", description="🗓 Compile digest previews now"),
    BotCommand(command="scrape", description="🔄 Scrape now (rss/webpage/…/all)"),
    BotCommand(command="ingest", description="📲 Manually ingest a vacancy"),
    BotCommand(command="listchannels", description="📡 Posting targets"),
    BotCommand(command="listsources", description="🗂 Source registry"),
    BotCommand(command="addsource", description="➕ Add source"),
    BotCommand(command="listfields", description="🔬 Field taxonomy"),
    BotCommand(command="ai_status", description="🤖 AI router status"),
    BotCommand(command="listtexts", description="🔤 Customize bot texts"),
    BotCommand(command="broadcast", description="📢 Message all users"),
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
    dp.include_router(texts.router)
    dp.include_router(channels.router)
    dp.include_router(admin_help.router)
    dp.include_router(start.router)
    dp.include_router(documents.router)
    dp.include_router(search.router)
    dp.include_router(saved.router)
    dp.include_router(analyze.router)
    dp.include_router(forward.router)
    return dp


async def set_bot_commands(bot: Bot) -> None:
    # English is the default menu; Armenian Telegram clients get the hy menu.
    await bot.set_my_commands(student_commands("en"), scope=BotCommandScopeDefault())
    await bot.set_my_commands(student_commands("hy"), scope=BotCommandScopeDefault(),
                              language_code="hy")
    admin_menu = student_commands("en") + ADMIN_EXTRA_COMMANDS
    for admin_id in get_settings().admin_ids:
        try:
            await bot.set_my_commands(admin_menu, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            log.warning("admin_commands_failed", admin=admin_id, error=str(e)[:150])
