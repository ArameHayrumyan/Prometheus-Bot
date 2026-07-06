"""Saved opportunities: ⭐ save, /saved list, applied flag, reminder mute,
outcome recording. Reminders themselves are sent by the scheduler."""
import html
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import kb
from app.db.models import Opportunity, SavedOpportunity, User
from app.i18n import t
from app.logging_setup import get_logger

router = Router()
log = get_logger("bot.saved")


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


async def save_opportunity(session: AsyncSession, user: User, opp: Opportunity) -> bool:
    """Returns True if newly saved, False if it was already saved."""
    existing = (await session.execute(
        select(SavedOpportunity).where(
            SavedOpportunity.user_tg_id == user.tg_id,
            SavedOpportunity.opportunity_id == opp.id,
        )
    )).scalar_one_or_none()
    if existing is not None:
        return False
    session.add(SavedOpportunity(user_tg_id=user.tg_id, opportunity_id=opp.id))
    await session.flush()
    return True


async def handle_save(message: Message, session: AsyncSession, user: User,
                      opp: Opportunity) -> None:
    fresh = await save_opportunity(session, user, opp)
    key = "saved_ok" if fresh else "saved_dup"
    await message.answer(t(key, user.language, title=opp.title[:80]))


@router.callback_query(F.data.startswith("sv:"))
async def cb_save(query: CallbackQuery, session: AsyncSession, user: User):
    opp = await session.get(Opportunity, int(query.data.split(":")[1]))
    if opp is None:
        await query.answer("✖️")
        return
    fresh = await save_opportunity(session, user, opp)
    await query.answer(t("saved_ok_short" if fresh else "saved_dup_short", user.language),
                       show_alert=False)


@router.message(Command("saved"))
async def cmd_saved(message: Message, session: AsyncSession, user: User):
    await _saved_list(message, session, user, edit=False)


async def _saved_list(message: Message, session: AsyncSession, user: User, edit: bool):
    lang = user.language
    rows = (await session.execute(
        select(SavedOpportunity, Opportunity)
        .join(Opportunity, Opportunity.id == SavedOpportunity.opportunity_id)
        .where(SavedOpportunity.user_tg_id == user.tg_id)
        .order_by(Opportunity.deadline.is_(None), Opportunity.deadline)
        .limit(20)
    )).all()
    if not rows:
        text = t("saved_empty", lang)
        if edit:
            try:
                await message.edit_text(text)
                return
            except Exception:
                pass
        await message.answer(text)
        return
    lines = [f"<b>{t('saved_title', lang)}</b>", ""]
    buttons: list[list[tuple[str, str]]] = []
    for i, (saved, opp) in enumerate(rows, 1):
        marks = []
        if saved.applied_at:
            marks.append("✅")
        if not saved.remind:
            marks.append("🔕")
        deadline = f"📅 {opp.deadline}" if opp.deadline else ""
        lines.append(f"{i}. <b>{_esc(opp.title[:70])}</b> {deadline} {' '.join(marks)}")
        bell = "🔕" if saved.remind else "🔔"
        applied = "↩️✅" if saved.applied_at else t("btn_applied", lang)
        buttons.append([
            (f"{i} ℹ️", f"svd:{saved.id}"),
            (f"{i} {applied}", f"svapp:{saved.id}"),
            (f"{i} {bell}", f"svmute:{saved.id}"),
            (f"{i} 🗑", f"svdel:{saved.id}"),
        ])
    text = "\n".join(lines)[:4096]
    markup = kb(buttons)
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def _owned(session: AsyncSession, saved_id: int, user: User) -> SavedOpportunity | None:
    saved = await session.get(SavedOpportunity, saved_id)
    return saved if saved is not None and saved.user_tg_id == user.tg_id else None


@router.callback_query(F.data.startswith("svd:"))
async def cb_saved_detail(query: CallbackQuery, session: AsyncSession, user: User):
    from app.bot.details import build_detail_text
    from app.db.settings_service import get_setting

    saved = await _owned(session, int(query.data.split(":")[1]), user)
    await query.answer()
    if saved is None:
        return
    opp = await session.get(Opportunity, saved.opportunity_id)
    if opp is None:
        return
    weights = await get_setting(session, "scoring_weights")
    await query.message.answer(
        build_detail_text(opp, user, weights), parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=kb([[(t("btn_analyze", user.language), f"fit:{opp.id}")]]),
    )


@router.callback_query(F.data.startswith("svapp:"))
async def cb_applied(query: CallbackQuery, session: AsyncSession, user: User):
    saved = await _owned(session, int(query.data.split(":")[1]), user)
    if saved is None:
        await query.answer()
        return
    if saved.applied_at is None:
        saved.applied_at = datetime.now(timezone.utc)
        await query.answer(t("applied_ok", user.language), show_alert=True)
    else:
        saved.applied_at = None
        saved.outcome = None
        saved.outcome_asked_at = None
        await query.answer(t("applied_undo", user.language))
    await session.flush()
    await _saved_list(query.message, session, user, edit=True)


@router.callback_query(F.data.startswith("svmute:"))
async def cb_mute(query: CallbackQuery, session: AsyncSession, user: User):
    saved = await _owned(session, int(query.data.split(":")[1]), user)
    if saved is None:
        await query.answer()
        return
    saved.remind = not saved.remind
    await session.flush()
    await query.answer(t("mute_ok" if not saved.remind else "unmute_ok", user.language))
    if query.message.text and t("saved_title", user.language) in (query.message.text or ""):
        await _saved_list(query.message, session, user, edit=True)


@router.callback_query(F.data.startswith("svdel:"))
async def cb_delete(query: CallbackQuery, session: AsyncSession, user: User):
    saved = await _owned(session, int(query.data.split(":")[1]), user)
    if saved is not None:
        await session.delete(saved)
        await session.flush()
    await query.answer(t("saved_removed", user.language))
    await _saved_list(query.message, session, user, edit=True)


@router.callback_query(F.data.startswith("svout:"))
async def cb_outcome(query: CallbackQuery, session: AsyncSession, user: User):
    _, saved_id, value = query.data.split(":")
    saved = await _owned(session, int(saved_id), user)
    await query.answer()
    if saved is None:
        return
    now = datetime.now(timezone.utc)
    if value == "waiting":
        saved.outcome_asked_at = now  # re-asked after another 30 days
        reply = t("outcome_thanks_waiting", user.language)
    else:
        saved.outcome = value  # accepted / rejected
        saved.outcome_asked_at = now
        reply = t(f"outcome_thanks_{value}", user.language)
    await session.flush()
    try:
        await query.message.edit_text(reply)
    except Exception:
        await query.message.answer(reply)
