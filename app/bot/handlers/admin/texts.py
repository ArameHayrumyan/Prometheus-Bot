"""Live text customization (/settext family) and /broadcast.

Every user-facing string (posts, buttons, DMs, digests) is an i18n key;
overrides live in app_settings "i18n_overrides" and apply instantly —
text/emoji only, zero logic changes, survives restarts and redeploys.
"""
import asyncio
import html

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin import IsAdmin
from app.bot.keyboards import kb
from app.db.models import AdminAction, User
from app.db.settings_service import get_setting, set_setting
from app.i18n import base_keys, base_value, get_overrides, set_overrides
from app.logging_setup import get_logger

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
log = get_logger("bot.admin.texts")

LANGS = ("en", "hy")


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


async def _save_overrides(session: AsyncSession, overrides: dict) -> None:
    await set_setting(session, "i18n_overrides", overrides)
    set_overrides(overrides)  # refresh the in-memory map immediately


@router.message(Command("settext"))
async def cmd_settext(message: Message, command: CommandObject, session: AsyncSession):
    args = (command.args or "").split(maxsplit=2)
    if len(args) < 3 or args[0] not in LANGS:
        await message.answer(
            "Usage: <code>/settext &lt;en|hy&gt; &lt;key&gt; &lt;new text&gt;</code>\n"
            "HTML and emojis allowed; keep the {placeholders} of the original.\n"
            "Find keys with /listtexts [filter], inspect with /gettext &lt;key&gt;.",
            parse_mode="HTML")
        return
    lang, key, text = args
    if key not in base_keys():
        await message.answer(f"Unknown key «{key}». See /listtexts.")
        return
    overrides = dict(get_overrides())
    overrides.setdefault(lang, {})
    overrides[lang] = dict(overrides[lang])
    overrides[lang][key] = text
    await _save_overrides(session, overrides)
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="settext",
                            payload={"lang": lang, "key": key}))
    await message.answer(f"✅ <b>{key}</b> [{lang}] is now:\n\n{text}",
                         parse_mode="HTML")


@router.message(Command("gettext"))
async def cmd_gettext(message: Message, command: CommandObject):
    key = (command.args or "").strip()
    if key not in base_keys():
        await message.answer("Usage: /gettext <key>   (see /listtexts)")
        return
    overrides = get_overrides()
    lines = [f"🔤 <b>{key}</b>"]
    for lang in LANGS:
        override = (overrides.get(lang) or {}).get(key)
        base = base_value(key, lang) or "—"
        if override:
            lines.append(f"\n[{lang}] (customized):\n{override}")
            lines.append(f"[{lang}] original:\n<s>{_esc(base)}</s>")
        else:
            lines.append(f"\n[{lang}] (default):\n{_esc(base)}")
    lines.append("\nChange: /settext <lang> " + key + " <text>")
    lines.append("Reset: /resettext <lang> " + key)
    await message.answer("\n".join(lines)[:4096], parse_mode="HTML")


@router.message(Command("resettext"))
async def cmd_resettext(message: Message, command: CommandObject, session: AsyncSession):
    args = (command.args or "").split()
    if len(args) != 2 or args[0] not in LANGS:
        await message.answer("Usage: /resettext <en|hy> <key>")
        return
    lang, key = args
    overrides = dict(get_overrides())
    if key in (overrides.get(lang) or {}):
        overrides[lang] = {k: v for k, v in overrides[lang].items() if k != key}
        await _save_overrides(session, overrides)
        await message.answer(f"↩️ «{key}» [{lang}] reset to default.")
    else:
        await message.answer(f"«{key}» [{lang}] has no customization.")


@router.message(Command("listtexts"))
async def cmd_listtexts(message: Message, command: CommandObject):
    needle = (command.args or "").strip().lower()
    overrides = get_overrides()
    lines = ["🔤 <b>Text keys</b> (✏️ = customized). /gettext <key> for details.", ""]
    for key in base_keys():
        if needle and needle not in key.lower() \
                and needle not in (base_value(key) or "").lower():
            continue
        marks = "".join(
            "✏️" for lang in LANGS if key in (overrides.get(lang) or {})
        )
        preview = (base_value(key) or "").replace("\n", " ")[:40]
        lines.append(f"<code>{key}</code> {marks} — {_esc(preview)}")
    text = "\n".join(lines)
    for i in range(0, len(text), 3900):
        await message.answer(text[i:i + 3900], parse_mode="HTML")


# ---------------------------------------------------------------- broadcast --

class Broadcast(StatesGroup):
    confirm = State()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject, state: FSMContext):
    text = (command.args or "").strip()
    if not text:
        await message.answer(
            "Usage: /broadcast <message>\n"
            "Sends a DM to every bot user. You'll get a preview + confirm first.")
        return
    await state.set_state(Broadcast.confirm)
    await state.update_data(broadcast_text=text)
    await message.answer(
        f"📢 Broadcast preview:\n\n{_esc(text)}\n\nSend to ALL users?",
        parse_mode="HTML",
        reply_markup=kb([[("📤 Send to everyone", "bc:go"), ("✖️ Cancel", "bc:no")]]))


@router.callback_query(F.data == "bc:no", Broadcast.confirm)
async def cb_broadcast_cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.answer("Cancelled")
    await query.message.edit_text("Broadcast cancelled.")


@router.callback_query(F.data == "bc:go", Broadcast.confirm)
async def cb_broadcast_go(query: CallbackQuery, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()
    await query.answer("Sending…")
    user_ids = list((await session.execute(select(User.tg_id))).scalars().all())
    sent = failed = 0
    for uid in user_ids:
        try:
            await query.bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # stay far below Telegram's ~30 msg/s limit
    session.add(AdminAction(admin_tg_id=query.from_user.id, action="broadcast",
                            payload={"sent": sent, "failed": failed}))
    log.info("broadcast_done", sent=sent, failed=failed)
    await query.message.edit_text(
        f"📤 Broadcast done: {sent} delivered, {failed} failed/blocked.")
