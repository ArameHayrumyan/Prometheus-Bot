"""Field taxonomy management: /addfield, /listfields, /togglefield."""
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin import IsAdmin
from app.db.models import AdminAction, FieldTaxonomy

router = Router()
router.message.filter(IsAdmin())


@router.message(Command("addfield"))
async def cmd_addfield(message: Message, command: CommandObject, session: AsyncSession):
    # /addfield Robotics | robotics, ros, autonomous systems
    raw = command.args or ""
    if "|" not in raw:
        await message.answer(
            "Usage: <code>/addfield Name | keyword1, keyword2, ...</code>\n"
            "Example: <code>/addfield Robotics | robotics, ros, autonomous</code>",
            parse_mode="HTML")
        return
    name, kw_raw = (part.strip() for part in raw.split("|", 1))
    keywords = [k.strip().lower() for k in kw_raw.split(",") if k.strip()]
    if not name or not keywords:
        await message.answer("Both a name and at least one keyword are required.")
        return
    existing = (await session.execute(
        select(FieldTaxonomy).where(FieldTaxonomy.name == name)
    )).scalar_one_or_none()
    if existing is not None:
        existing.keywords = sorted(set(existing.keywords) | set(keywords))
        existing.active = True
        await message.answer(f"✅ Updated field «{name}»: {existing.keywords}")
    else:
        session.add(FieldTaxonomy(name=name, keywords=keywords, active=True))
        await message.answer(f"✅ Added field «{name}»: {keywords}")
    session.add(AdminAction(admin_tg_id=message.from_user.id, action="field_add",
                            payload={"name": name, "keywords": keywords}))


@router.message(Command("listfields"))
async def cmd_listfields(message: Message, session: AsyncSession):
    rows = (await session.execute(select(FieldTaxonomy).order_by(FieldTaxonomy.id))).scalars().all()
    lines = ["🔬 <b>Field taxonomy</b>", ""]
    for f in rows:
        mark = "🟢" if f.active else "⚪️"
        lines.append(f"{mark} #{f.id} <b>{f.name}</b>: {', '.join(f.keywords[:8])}"
                     + ("…" if len(f.keywords) > 8 else ""))
    await message.answer("\n".join(lines)[:4096], parse_mode="HTML")


@router.message(Command("togglefield"))
async def cmd_togglefield(message: Message, command: CommandObject, session: AsyncSession):
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Usage: /togglefield <id>")
        return
    field = await session.get(FieldTaxonomy, int(arg))
    if field is None:
        await message.answer("No such field.")
        return
    field.active = not field.active
    await message.answer(f"Field «{field.name}» is now {'🟢 active' if field.active else '⚪️ inactive'}.")
