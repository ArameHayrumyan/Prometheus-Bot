"""Source registry management: /addsource, /listsources, /togglesource, /scrape."""
import asyncio

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin import IsAdmin
from app.constants import SourceType
from app.db.models import AdminAction, Source
from app.scheduler.jobs import run_source_types

router = Router()
router.message.filter(IsAdmin())

USAGE = (
    "Usage: <code>/addsource &lt;type&gt; &lt;url&gt; [category] [name...]</code>\n"
    f"Types: {', '.join(s.value for s in SourceType)}\n"
    "Examples:\n"
    "<code>/addsource rss https://example.org/feed/ aggregator Example feed</code>\n"
    "<code>/addsource webpage https://uni.edu/scholarships university Uni bulletin</code>\n"
    "Add <code>js</code> as category suffix (e.g. <code>company:js</code>) for "
    "Playwright rendering."
)


@router.message(Command("addsource"))
async def cmd_addsource(message: Message, command: CommandObject, session: AsyncSession):
    args = (command.args or "").split()
    if len(args) < 2:
        await message.answer(USAGE, parse_mode="HTML")
        return
    stype, url = args[0].lower(), args[1]
    if stype not in [s.value for s in SourceType]:
        await message.answer(f"Unknown type «{stype}».\n\n{USAGE}", parse_mode="HTML")
        return
    if not url.startswith(("http://", "https://", "imap://")):
        await message.answer("URL must start with http(s):// or imap://")
        return
    category = args[2] if len(args) > 2 else "general"
    needs_js = category.endswith(":js")
    category = category.removesuffix(":js")
    name = " ".join(args[3:]) if len(args) > 3 else url[:80]

    source = Source(name=name, source_type=stype, url=url,
                    category=category, needs_js=needs_js, active=True)
    session.add(source)
    await session.flush()
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="source_add",
                            payload={"source_id": source.id, "url": url}))
    await message.answer(
        f"✅ Source #{source.id} added: <b>{name}</b>\n"
        f"type={stype}, category={category}, js={needs_js}\n"
        "It will be picked up on the next scheduled run.",
        parse_mode="HTML",
    )


@router.message(Command("listsources"))
async def cmd_listsources(message: Message, session: AsyncSession):
    sources = (await session.execute(
        select(Source).order_by(Source.source_type, Source.id)
    )).scalars().all()
    lines = [f"🗂 <b>Source registry</b> ({len(sources)} targets)", ""]
    for s in sources:
        status = "🟢" if s.active else "⚪️"
        checked = s.last_checked_at.strftime("%m-%d %H:%M") if s.last_checked_at else "never"
        lines.append(f"{status} #{s.id} [{s.source_type}] {s.name[:45]} (checked: {checked})")
    # Telegram 4096 limit — send in chunks
    text = "\n".join(lines)
    for i in range(0, len(text), 3900):
        await message.answer(text[i:i + 3900], parse_mode="HTML" if i == 0 else None)


@router.message(Command("scrape"))
async def cmd_scrape(message: Message, command: CommandObject):
    """Trigger a scrape cycle immediately instead of waiting for the scheduler."""
    valid = [s.value for s in SourceType]
    arg = (command.args or "rss").strip().lower()
    types = valid if arg == "all" else [arg]
    if arg != "all" and arg not in valid:
        await message.answer(f"Usage: /scrape <{'|'.join(valid)}|all>\n"
                             "Default: rss. «all» can take many minutes "
                             "(polite per-domain spacing across ~100 sources).")
        return
    await message.answer(f"🔄 Scraping now: {', '.join(types)} — I'll DM you when the "
                         "cycle finishes.")
    bot = message.bot
    chat_id = message.chat.id

    async def run():
        try:
            n = await run_source_types(bot, types, notify_admins=False)
            summary = (f"✅ Cycle done ({', '.join(types)}): {n} new item(s) queued — /queue"
                       if n else
                       f"✅ Cycle done ({', '.join(types)}): nothing new queued. "
                       "/discards shows what was filtered; duplicates of already-seen "
                       "items are skipped silently.")
            await bot.send_message(chat_id, summary)
        except Exception as e:
            await bot.send_message(chat_id, f"⚠️ Scrape cycle failed: {str(e)[:300]}")

    asyncio.create_task(run())


@router.message(Command("sourcemeta"))
async def cmd_sourcemeta(message: Message, command: CommandObject, session: AsyncSession):
    """Per-source tuning without code: /sourcemeta <id> <key> <value> ('-' deletes).
    Most useful key: selector — a CSS selector scoping webpage extraction,
    e.g. /sourcemeta 12 selector div.jobs-list"""
    args = (command.args or "").split(maxsplit=2)
    if len(args) < 3 or not args[0].isdigit():
        await message.answer(
            "Usage: <code>/sourcemeta &lt;id&gt; &lt;key&gt; &lt;value&gt;</code> "
            "(value <code>-</code> removes the key)\n"
            "Example: <code>/sourcemeta 12 selector div.jobs-list</code> — scope "
            "that source's scraping to the matching container.\n"
            "Find ids with /listsources.",
            parse_mode="HTML")
        return
    source = await session.get(Source, int(args[0]))
    if source is None:
        await message.answer("No such source.")
        return
    key, value = args[1], args[2].strip()
    meta = dict(source.meta or {})
    if value == "-":
        meta.pop(key, None)
    else:
        meta[key] = value
    source.meta = meta  # reassign so JSONB change is tracked
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="source_meta",
                            payload={"source_id": source.id, "key": key, "value": value}))
    await message.answer(
        f"✅ Source #{source.id} meta: <code>{meta}</code>\n"
        "Applies on the next scrape (/scrape to test now).", parse_mode="HTML")


@router.message(Command("togglesource"))
async def cmd_togglesource(message: Message, command: CommandObject, session: AsyncSession):
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Usage: /togglesource <id>")
        return
    source = await session.get(Source, int(arg))
    if source is None:
        await message.answer("No such source.")
        return
    source.active = not source.active
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="source_toggle",
                            payload={"source_id": source.id, "active": source.active}))
    await message.answer(f"Source #{source.id} is now {'🟢 active' if source.active else '⚪️ inactive'}.")
