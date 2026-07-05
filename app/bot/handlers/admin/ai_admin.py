"""Live AI-router admin: /ai_status, /ai_setpriority, /ai_enable, /ai_disable,
plus scoring tunables: /setweight, /setband, /setminduration."""
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import get_router
from app.bot.handlers.admin import IsAdmin
from app.db.models import AdminAction
from app.db.settings_service import get_setting, set_setting

router = Router()
router.message.filter(IsAdmin())

PROVIDERS = ("groq", "deepseek", "gemini")


@router.message(Command("ai_status"))
async def cmd_ai_status(message: Message, session: AsyncSession):
    priority = await get_setting(session, "ai_priority")
    disabled = await get_setting(session, "ai_disabled")
    lines = [
        "🤖 <b>AI router</b>",
        f"Priority: {' → '.join(priority)}",
        f"Disabled: {', '.join(disabled) or 'none'}",
        "",
    ]
    for s in get_router().status():
        mark = "🔴 disabled" if s["name"] in disabled else (
            "🟢" if s["configured"] else "⚪️ no key")
        lines.append(
            f"{mark} <b>{s['name']}</b> — req: {s['requests']}, errors: {s['errors']} "
            f"(1h: {s['errors_last_hour']}), 429s: {s['rate_limits']}"
        )
        if s["last_error"]:
            lines.append(f"   last: <i>{s['last_error'][:150]}</i>")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("ai_setpriority"))
async def cmd_ai_setpriority(message: Message, command: CommandObject, session: AsyncSession):
    raw = (command.args or "").replace("→", " ").replace(">", " ").replace(",", " ")
    order = [p.strip().lower() for p in raw.split() if p.strip()]
    if not order or any(p not in PROVIDERS for p in order):
        await message.answer(
            "Usage: /ai_setpriority groq deepseek gemini\n"
            f"Valid providers: {', '.join(PROVIDERS)}")
        return
    await set_setting(session, "ai_priority", order)
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="ai_priority",
                            payload={"order": order}))
    await message.answer(f"✅ Priority: {' → '.join(order)} (live, no redeploy)")


async def _toggle(message: Message, session: AsyncSession, name: str, disable: bool):
    name = name.strip().lower()
    if name not in PROVIDERS:
        await message.answer(f"Unknown provider. Valid: {', '.join(PROVIDERS)}")
        return
    disabled: list = list(await get_setting(session, "ai_disabled"))
    if disable and name not in disabled:
        disabled.append(name)
    elif not disable and name in disabled:
        disabled.remove(name)
    await set_setting(session, "ai_disabled", disabled)
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="ai_toggle",
                            payload={"provider": name, "disabled": disable}))
    await message.answer(f"✅ {name} {'disabled' if disable else 'enabled'}.")


@router.message(Command("ai_disable"))
async def cmd_ai_disable(message: Message, command: CommandObject, session: AsyncSession):
    await _toggle(message, session, command.args or "", disable=True)


@router.message(Command("ai_enable"))
async def cmd_ai_enable(message: Message, command: CommandObject, session: AsyncSession):
    await _toggle(message, session, command.args or "", disable=False)


@router.message(Command("setweight"))
async def cmd_setweight(message: Message, command: CommandObject, session: AsyncSession):
    args = (command.args or "").split()
    weights: dict = dict(await get_setting(session, "scoring_weights"))
    if len(args) != 2 or args[0] not in weights:
        await message.answer(
            f"Usage: /setweight <{'|'.join(weights)}> <0..1>\nCurrent: {weights}")
        return
    try:
        weights[args[0]] = float(args[1])
    except ValueError:
        await message.answer("Weight must be a number.")
        return
    await set_setting(session, "scoring_weights", weights)
    await message.answer(f"✅ Weights: {weights}")


@router.message(Command("setband"))
async def cmd_setband(message: Message, command: CommandObject, session: AsyncSession):
    args = (command.args or "").split()
    if len(args) != 2 or not all(a.isdigit() for a in args):
        band = await get_setting(session, "borderline_band")
        await message.answer(f"Usage: /setband <low> <high>\nCurrent AI-tiebreak band: {band}")
        return
    lo, hi = sorted(int(a) for a in args)
    await set_setting(session, "borderline_band", [lo, hi])
    await message.answer(f"✅ Borderline band: [{lo}, {hi}]")


@router.message(Command("setminduration"))
async def cmd_setminduration(message: Message, command: CommandObject, session: AsyncSession):
    arg = (command.args or "").strip()
    if not arg.isdigit():
        current = await get_setting(session, "min_duration_days")
        await message.answer(f"Usage: /setminduration <days>\nCurrent: {current}")
        return
    await set_setting(session, "min_duration_days", int(arg))
    await message.answer(f"✅ Minimum duration: {arg} days")
