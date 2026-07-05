"""'Analyze my fit' — callback + deep-link entry, shared by forward flow."""
import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.fit import analyze_fit, has_resume
from app.db.models import Opportunity, User
from app.i18n import t
from app.logging_setup import get_logger

router = Router()
log = get_logger("bot.analyze")


def format_fit(result: dict, opp_title: str, lang: str) -> str:
    lines = [
        f"<b>{t('analyze_header', lang, title=html.escape(opp_title[:150], quote=False))}</b>",
        "",
        f"<b>{t('analyze_score', lang, score=result['match_score'])}</b>",
    ]
    if result.get("gaps"):
        lines += ["", f"<b>{t('analyze_gaps', lang)}</b>"]
        lines += [f"• {html.escape(g, quote=False)}" for g in result["gaps"]]
    if result.get("suggestions"):
        lines += ["", f"<b>{t('analyze_suggestions', lang)}</b>"]
        lines += [f"• {html.escape(s, quote=False)}" for s in result["suggestions"]]
    if result.get("resume_bullets"):
        lines += ["", f"<b>{t('analyze_bullets', lang)}</b>"]
        lines += [f"▸ <i>{html.escape(b, quote=False)}</i>" for b in result["resume_bullets"]]
    return "\n".join(lines)[:4096]


async def run_fit_analysis(message: Message, session: AsyncSession,
                           user: User, opp: Opportunity) -> None:
    if not await has_resume(session, user.tg_id):
        await message.answer(t("analyze_no_resume", user.language))
        return
    progress = await message.answer(t("analyze_working", user.language))
    try:
        result = await analyze_fit(session, user, opp)
    except Exception as e:
        log.warning("fit_failed", user=user.tg_id, opp=opp.id, error=str(e)[:200])
        await progress.edit_text(t("analyze_failed", user.language))
        return
    await progress.edit_text(format_fit(result, opp.title, user.language),
                             parse_mode="HTML")


@router.callback_query(F.data.startswith("fit:"))
async def cb_fit(query: CallbackQuery, session: AsyncSession, user: User):
    opp = await session.get(Opportunity, int(query.data.split(":")[1]))
    await query.answer()
    if opp is None:
        await query.message.answer(t("forward_not_found", user.language))
        return
    await run_fit_analysis(query.message, session, user, opp)
