"""Forward-to-bot wrap-up (§12): forwarded channel post -> full detail card
(+ automatic fit analysis when a resume is on file).
"""
from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.fit import has_resume
from app.bot.details import build_detail_text
from app.bot.forward_match import resolve_forwarded
from app.bot.handlers.analyze import run_fit_analysis
from app.bot.keyboards import kb
from app.db.models import User
from app.db.settings_service import get_setting
from app.i18n import t

router = Router()


@router.message(F.forward_origin)
async def on_forward(message: Message, session: AsyncSession, user: User):
    origin = message.forward_origin
    chat_id = getattr(getattr(origin, "chat", None), "id", None)
    message_id = getattr(origin, "message_id", None)
    text = message.text or message.caption
    opp = await resolve_forwarded(session, chat_id, message_id, text)
    if opp is None:
        await message.answer(t("forward_not_found", user.language))
        return
    weights = await get_setting(session, "scoring_weights")
    await message.answer(
        build_detail_text(opp, user, weights),
        parse_mode="HTML", disable_web_page_preview=True,
        reply_markup=kb([[(t("btn_analyze", user.language), f"fit:{opp.id}"),
                          (t("btn_save", user.language), f"sv:{opp.id}")]]),
    )
    if await has_resume(session, user.tg_id):
        await run_fit_analysis(message, session, user, opp)
