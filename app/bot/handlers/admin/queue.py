"""Admin review queue (§9): approve / reject / edit, discard log, stats."""
import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin import IsAdmin
from app.bot.keyboards import kb
from app.bot.posting import (build_post_text, notify_saved_filters,
                             publish_opportunity)
from app.bot.states import AdminEdit
from app.constants import OppStatus
from app.db.models import AdminAction, Opportunity
from app.logging_setup import get_logger

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
log = get_logger("bot.admin.queue")


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def queue_card(opp: Opportunity, pending_total: int) -> str:
    flags = []
    if opp.armenian_eligibility == "UNCERTAIN":
        flags.append("⚠️ <b>UNCERTAIN Armenian eligibility</b> — verify before approving")
    if opp.ai_verdict:
        v = opp.ai_verdict
        flags.append(f"🤖 AI tiebreak: {v.get('verdict')} ({v.get('confidence')}%) — {_esc(v.get('reason', ''))}")
    lines = [
        f"📥 <b>Review queue</b> ({pending_total} pending) — #opp{opp.id}",
        "",
        f"<b>{_esc(opp.title)}</b>",
        f"🏛 {_esc(opp.org or 'unknown org')} | {opp.opportunity_type} | {opp.funding_tier}",
        f"🎓 {', '.join(opp.degree_levels or [])} | 🔬 {', '.join(opp.fields or [])}",
        f"📅 deadline: {opp.deadline or '—'} | ⏱ {opp.duration_days or '—'}d",
        f"⚖️ legitimacy: {opp.legitimacy_score} | 🎯 chance: {opp.chance_percent}%",
        f"🔗 {_esc(opp.url)}",
        "",
        _esc(opp.description[:800]),
    ]
    if flags:
        lines.insert(1, "\n".join(flags))
    return "\n".join(lines)[:4096]


def queue_kb(opp_id: int):
    return kb([
        [("✅ Approve", f"adm:approve:{opp_id}"),
         ("❌ Reject", f"adm:reject:{opp_id}")],
        [("✏️ Edit", f"adm:edit:{opp_id}"),
         ("⏭ Skip", f"adm:skip:{opp_id}")],
    ])


async def _next_pending(session: AsyncSession, after_id: int = 0) -> tuple[Opportunity | None, int]:
    total = (await session.execute(
        select(func.count()).select_from(Opportunity)
        .where(Opportunity.status == OppStatus.PENDING_REVIEW)
    )).scalar_one()
    opp = (await session.execute(
        select(Opportunity)
        .where(Opportunity.status == OppStatus.PENDING_REVIEW, Opportunity.id > after_id)
        .order_by(Opportunity.id)
        .limit(1)
    )).scalar_one_or_none()
    return opp, total


async def show_queue(message: Message, session: AsyncSession, after_id: int = 0,
                     edit: bool = False):
    opp, total = await _next_pending(session, after_id)
    if opp is None:
        text = "📭 Review queue is empty."
        await (message.edit_text(text) if edit else message.answer(text))
        return
    text = queue_card(opp, total)
    markup = queue_kb(opp.id)
    if edit:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML",
                                disable_web_page_preview=True)
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML",
                             disable_web_page_preview=True)


@router.message(Command("queue"))
async def cmd_queue(message: Message, session: AsyncSession):
    await show_queue(message, session)


@router.callback_query(F.data.startswith("adm:"))
async def cb_admin(query: CallbackQuery, session: AsyncSession, state: FSMContext):
    _, action, opp_id_s = query.data.split(":")
    opp_id = int(opp_id_s)
    opp = await session.get(Opportunity, opp_id)
    if opp is None:
        await query.answer("Gone")
        return

    if action == "skip":
        await query.answer()
        await show_queue(query.message, session, after_id=opp_id, edit=True)
        return

    if action == "reject":
        opp.status = OppStatus.REJECTED
        session.add(AdminAction(admin_tg_id=query.from_user.id, opportunity_id=opp.id,
                                action="reject"))
        await session.flush()
        await query.answer("Rejected")
        await show_queue(query.message, session, edit=True)
        return

    if action == "approve":
        session.add(AdminAction(admin_tg_id=query.from_user.id, opportunity_id=opp.id,
                                action="approve"))
        opp.status = OppStatus.APPROVED
        posted = await publish_opportunity(query.bot, session, opp)
        await session.flush()
        await query.answer(f"Published to {posted} channel(s)")
        if posted:
            await notify_saved_filters(query.bot, session, opp)
        await show_queue(query.message, session, edit=True)
        return

    if action == "edit":
        await state.set_state(AdminEdit.waiting_text)
        await state.update_data(edit_opp_id=opp_id)
        await query.answer()
        await query.message.answer(
            f"✏️ Editing #opp{opp_id}. Send the new post <b>body</b> text "
            "(HTML allowed). The Apply/Details/Analyze buttons and the #opp tag "
            "are auto-generated and cannot be edited. Send /cancel to abort.",
            parse_mode="HTML",
        )


@router.message(Command("cancel"), AdminEdit.waiting_text)
@router.message(Command("cancel"), AdminEdit.waiting_photo)
async def cancel_edit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Edit cancelled.")


@router.message(AdminEdit.waiting_text)
async def edit_text(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    opp = await session.get(Opportunity, data["edit_opp_id"])
    if opp is None:
        await state.clear()
        return
    opp.edited_text = (message.html_text or message.text or "")[:3000]
    session.add(AdminAction(admin_tg_id=message.from_user.id, opportunity_id=opp.id,
                            action="edit", payload={"field": "text"}))
    await session.flush()
    await state.set_state(AdminEdit.waiting_photo)
    await message.answer(
        "Body updated. Now send an <b>image</b> for the post, or /skip to keep none, "
        "or /cancel.", parse_mode="HTML",
    )


@router.message(Command("skip"), AdminEdit.waiting_photo)
async def edit_skip_photo(message: Message, session: AsyncSession, state: FSMContext):
    await _finish_edit(message, session, state)


@router.message(AdminEdit.waiting_photo, F.photo)
async def edit_photo(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    opp = await session.get(Opportunity, data["edit_opp_id"])
    if opp is not None:
        opp.image_file_id = message.photo[-1].file_id
        session.add(AdminAction(admin_tg_id=message.from_user.id, opportunity_id=opp.id,
                                action="edit", payload={"field": "image"}))
        await session.flush()
    await _finish_edit(message, session, state)


async def _finish_edit(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    opp = await session.get(Opportunity, data["edit_opp_id"])
    await state.clear()
    if opp is None:
        return
    await message.answer("Preview:", parse_mode="HTML")
    await message.answer(build_post_text(opp)[:4096], parse_mode="HTML",
                         disable_web_page_preview=True)
    await message.answer("Use /queue to continue reviewing.",
                         reply_markup=queue_kb(opp.id))


@router.message(Command("discards"))
async def cmd_discards(message: Message, session: AsyncSession):
    rows = (await session.execute(
        select(Opportunity)
        .where(Opportunity.status == OppStatus.DISCARDED)
        .order_by(Opportunity.id.desc())
        .limit(15)
    )).scalars().all()
    if not rows:
        await message.answer("No discarded items.")
        return
    lines = ["🗑 <b>Last discarded items</b> (hard gate / low legitimacy / AI tiebreak):", ""]
    for opp in rows:
        lines.append(f"• <b>{_esc(opp.title[:80])}</b>\n  ↳ {_esc(opp.discard_reason or '')}")
    await message.answer("\n".join(lines)[:4096], parse_mode="HTML",
                         disable_web_page_preview=True)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    counts = dict((await session.execute(
        select(Opportunity.status, func.count()).group_by(Opportunity.status)
    )).all())
    lines = ["📊 <b>Pipeline stats</b>", ""]
    for status in ("PENDING_REVIEW", "APPROVED", "PUBLISHED", "REJECTED", "DISCARDED", "EXPIRED"):
        lines.append(f"{status}: {counts.get(status, 0)}")
    await message.answer("\n".join(lines), parse_mode="HTML")
