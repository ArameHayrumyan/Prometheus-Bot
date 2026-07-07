"""Free posting targets: /addchannel, /listchannels, /delchannel.

Free channels have no degree level and no audience routing — they appear as
extra (unchecked) toggles in every publish preview and receive only what the
admin explicitly selects. Targets can be plain channels or forum-supergroup
topics ("chat_id:thread_id").
"""
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin import IsAdmin
from app.constants import parse_channel_ref
from app.db.models import AdminAction, Channel

router = Router()
router.message.filter(IsAdmin())

USAGE = (
    "Usage: <code>/addchannel &lt;chat_id[:topic_id]&gt; &lt;name…&gt;</code>\n"
    "Examples:\n"
    "<code>/addchannel -1005555555555 Partners channel</code>\n"
    "<code>/addchannel -1005555555555:42 Jobs topic</code>  (forum topic)\n\n"
    "Add the bot as admin (Post messages) in the target first. The channel "
    "appears as an extra toggle in every publish preview — always unchecked, "
    "never auto-selected."
)


@router.message(Command("addchannel"))
async def cmd_addchannel(message: Message, command: CommandObject, session: AsyncSession):
    args = (command.args or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer(USAGE, parse_mode="HTML")
        return
    try:
        chat_id, thread_id = parse_channel_ref(args[0])
    except ValueError:
        await message.answer(USAGE, parse_mode="HTML")
        return
    name = args[1].strip()[:100]
    # verify the bot can actually post there before saving
    try:
        probe = await message.bot.send_message(
            chat_id, "✅ moonin: channel connected.", message_thread_id=thread_id)
        try:
            await message.bot.delete_message(chat_id, probe.message_id)
        except Exception:
            pass
    except Exception as e:
        await message.answer(
            f"⚠️ Can't post there: {str(e)[:200]}\n"
            "Is the bot an admin with Post messages in that chat/topic?")
        return
    channel = Channel(tg_channel_id=chat_id, thread_id=thread_id,
                      name=name, audience="free", degree_level_code=None)
    session.add(channel)
    await session.flush()
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="channel_add",
                            payload={"channel_id": channel.id, "chat": chat_id,
                                     "thread": thread_id}))
    await message.answer(
        f"✅ Channel #{channel.id} «{name}» added "
        f"({chat_id}{f':{thread_id}' if thread_id else ''}). "
        "It now appears in every publish preview as an unchecked toggle.")


@router.message(Command("listchannels"))
async def cmd_listchannels(message: Message, session: AsyncSession):
    channels = (await session.execute(
        select(Channel).order_by(Channel.audience, Channel.id)
    )).scalars().all()
    if not channels:
        await message.answer("No channels configured.")
        return
    icons = {"main": "🏠", "free": "📌"}
    lines = ["📡 <b>Posting targets</b>", ""]
    for c in channels:
        ref = f"{c.tg_channel_id}" + (f":{c.thread_id}" if c.thread_id else "")
        lines.append(f"{icons.get(c.audience, '•')} #{c.id} <b>{c.name or '—'}</b> "
                     f"[{c.audience}] <code>{ref}</code>")
    lines.append("")
    lines.append("🏠 main comes from env (CHANNEL_ID_MAIN); 📌 free ones via "
                 "/addchannel, removable with /delchannel <id>. All are equal "
                 "targets in the publish picker; only main is pre-checked.")
    await message.answer("\n".join(lines)[:4096], parse_mode="HTML")


@router.message(Command("navpost"))
async def cmd_navpost(message: Message, command: CommandObject, session: AsyncSession):
    """Generate/refresh the channel's pinned navigation index: all hashtag
    groups with tappable examples. Posts to main by default, or to the
    channel id given as argument (/listchannels for ids)."""
    from datetime import date

    from app.constants import DEGREE_LEVELS
    from app.constants import OpportunityType
    from app.db.models import FieldTaxonomy
    from app.bot.posting import _tag_slug
    from app.i18n import t

    arg = (command.args or "").strip()
    if arg.isdigit():
        channel = await session.get(Channel, int(arg))
    else:
        channel = (await session.execute(
            select(Channel).where(Channel.audience == "main")
        )).scalars().first()
    if channel is None:
        await message.answer("No target channel found — check /listchannels.")
        return

    fields = (await session.execute(
        select(FieldTaxonomy.name).where(FieldTaxonomy.active.is_(True))
    )).scalars().all()
    today = date.today()
    months = []
    for offset in range(4):  # current + next 3 months as examples
        m = (today.month - 1 + offset) % 12 + 1
        y = today.year + (today.month - 1 + offset) // 12
        months.append(date(y, m, 1).strftime("#%b%Y").lower())

    lines = [
        t("navpost_intro"),
        "",
        "🎓 " + " ".join(f"#{d}" for d in DEGREE_LEVELS) + " #youth",
        "🏷 " + " ".join(f"#{v}" for v in OpportunityType),
        "🔬 " + " ".join("#" + _tag_slug(f) for f in fields),
        "🌍 #remote #armenia #germany #usa …",
        "📅 " + " ".join(months) + " …",
    ]
    text = "\n".join(lines)[:4096]
    try:
        posted = await message.bot.send_message(
            channel.tg_channel_id, text, parse_mode="HTML",
            disable_web_page_preview=True, message_thread_id=channel.thread_id)
    except Exception as e:
        await message.answer(f"⚠️ Failed to post: {str(e)[:200]}")
        return
    pinned = False
    try:
        await message.bot.pin_chat_message(channel.tg_channel_id, posted.message_id,
                                           disable_notification=True)
        pinned = True
    except Exception:
        pass
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="navpost",
                            payload={"channel_id": channel.id}))
    await message.answer(
        "✅ Navigation post published" + (" and pinned." if pinned else
                                          ". Pin it manually (bot lacks pin rights)."))


@router.message(Command("delchannel"))
async def cmd_delchannel(message: Message, command: CommandObject, session: AsyncSession):
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Usage: /delchannel <id>  (see /listchannels; "
                             "only 📌 free channels can be removed)")
        return
    channel = await session.get(Channel, int(arg))
    if channel is None:
        await message.answer("No such channel.")
        return
    if channel.audience != "free":
        await message.answer("Only 📌 free channels can be removed — the 🏠 main "
                             "target comes from CHANNEL_ID_MAIN in env config.")
        return
    await session.delete(channel)
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="channel_del",
                            payload={"channel_id": int(arg)}))
    await message.answer(f"🗑 Channel #{arg} removed.")
