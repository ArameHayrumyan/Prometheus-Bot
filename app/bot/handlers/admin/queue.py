"""Admin review queue (§9): approve / reject / edit / photo / archive,
prev-next navigation, discard log, stats. Also the /archive shelf for
"review later" items.

Callback format: adm:<action>:<opp_id>:<mode> where mode is
'p' (pending queue) or 'a' (archive shelf).
"""
import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.enrich import enrich_opportunity
from app.bot.handlers.admin import IsAdmin
from app.bot.keyboards import kb
from app.bot.posting import (FUNDING_LABEL, TYPE_EMOJI, build_post_text,
                             notify_saved_filters, publish_opportunity)
from app.bot.states import AdminEdit
from app.constants import OppStatus
from app.db.models import AdminAction, Opportunity
from app.logging_setup import get_logger
from app.utils.text import smart_truncate

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
log = get_logger("bot.admin.queue")

MODE_STATUS = {"p": OppStatus.PENDING_REVIEW, "a": OppStatus.ARCHIVED}
MODE_TITLE = {"p": "📥 Review queue", "a": "🗂 Archive"}


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def queue_card(opp: Opportunity, total: int, mode: str) -> str:
    emoji = TYPE_EMOJI.get(opp.opportunity_type, "✨")
    lines = [
        f"{MODE_TITLE[mode]} · <b>{total}</b> item{'s' if total != 1 else ''}",
        f"{emoji} <b>{opp.opportunity_type.upper()}</b>  ·  #opp{opp.id}",
        "",
        f"<b>{_esc(opp.title)}</b>",
    ]
    if opp.org:
        lines.append(f"🏛 <i>{_esc(opp.org)}</i>")
    lines.append("")
    lines.append(f"<blockquote expandable>{_esc(smart_truncate(opp.description, 1500))}</blockquote>")
    lines.append("")
    facts = [
        f"💰 {FUNDING_LABEL.get(opp.funding_tier, opp.funding_tier)}",
        f"📅 {opp.deadline or 'no deadline stated'}   ⏱ {f'{opp.duration_days}d' if opp.duration_days else '—'}",
        f"🎓 {', '.join(opp.degree_levels or []) or '—'}",
        f"🔬 {', '.join(opp.fields or []) or '—'}",
        f"⚖️ legitimacy <b>{opp.legitimacy_score}</b>/100   🎯 chance ~<b>{opp.chance_percent}%</b>",
        f"🔗 {_esc(opp.url)}",
    ]
    lines.extend(facts)
    flags = []
    if opp.armenian_eligibility == "UNCERTAIN":
        flags.append("⚠️ <b>UNCERTAIN Armenian eligibility</b> — verify before approving")
    if opp.english_req_score is not None:
        flags.append(f"🇬🇧 requires {opp.english_req_test} {opp.english_req_score:g}")
    if opp.image_file_id:
        flags.append("🖼 photo attached")
    if opp.edited_text:
        flags.append("✏️ body edited")
    if opp.ai_verdict:
        v = opp.ai_verdict
        flags.append(f"🤖 AI tiebreak: {v.get('verdict')} ({v.get('confidence')}%) — "
                     f"<i>{_esc(str(v.get('reason', ''))[:150])}</i>")
    if flags:
        lines.append("")
        lines.extend(flags)
    return "\n".join(lines)[:4096]


def queue_kb(opp_id: int, mode: str = "p"):
    shelf = ("🗂 Later", f"adm:archive:{opp_id}:{mode}") if mode == "p" \
        else ("📥 Back to queue", f"adm:archive:{opp_id}:{mode}")
    return kb([
        [("✅ Approve", f"adm:approve:{opp_id}:{mode}"),
         ("❌ Reject", f"adm:reject:{opp_id}:{mode}")],
        [("✏️ Edit text", f"adm:edit:{opp_id}:{mode}"),
         ("🖼 Photo", f"adm:photo:{opp_id}:{mode}")],
        [("◀️", f"adm:prev:{opp_id}:{mode}"),
         shelf,
         ("▶️", f"adm:skip:{opp_id}:{mode}")],
    ])


async def _publish_now(query: CallbackQuery, session: AsyncSession,
                       opp: Opportunity, mode: str, note: str = "") -> None:
    session.add(AdminAction(admin_tg_id=query.from_user.id, opportunity_id=opp.id,
                            action="approve"))
    opp.status = OppStatus.APPROVED
    posted = await publish_opportunity(query.bot, session, opp)
    await session.flush()
    await query.answer(f"Published to {posted} channel(s) {note}".strip())
    if posted:
        await notify_saved_filters(query.bot, session, opp)
    await show_queue(query.message, session, mode, after_id=opp.id, edit=True)


async def _count(session: AsyncSession, mode: str) -> int:
    return (await session.execute(
        select(func.count()).select_from(Opportunity)
        .where(Opportunity.status == MODE_STATUS[mode])
    )).scalar_one()


async def _fetch_item(session: AsyncSession, mode: str, after_id: int = 0,
                      before_id: int | None = None) -> Opportunity | None:
    status = MODE_STATUS[mode]
    if before_id is not None:
        stmt = (select(Opportunity)
                .where(Opportunity.status == status, Opportunity.id < before_id)
                .order_by(Opportunity.id.desc()).limit(1))
    else:
        stmt = (select(Opportunity)
                .where(Opportunity.status == status, Opportunity.id > after_id)
                .order_by(Opportunity.id).limit(1))
    return (await session.execute(stmt)).scalar_one_or_none()


async def show_queue(message: Message, session: AsyncSession, mode: str = "p",
                     after_id: int = 0, before_id: int | None = None,
                     edit: bool = False):
    total = await _count(session, mode)
    opp = await _fetch_item(session, mode, after_id, before_id)
    if opp is None and (after_id or before_id is not None):
        # wrapped past either end — restart from the beginning
        opp = await _fetch_item(session, mode, 0, None)
    if opp is None:
        text = "📭 Review queue is empty." if mode == "p" else "🗂 Archive is empty."
        if edit:
            try:
                await message.edit_text(text)
                return
            except Exception:
                pass
        await message.answer(text)
        return
    text = queue_card(opp, total, mode)
    markup = queue_kb(opp.id, mode)
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup, parse_mode="HTML",
                                    disable_web_page_preview=True)
            return
        except Exception:
            pass  # e.g. previous message was a photo preview -> send fresh
    await message.answer(text, reply_markup=markup, parse_mode="HTML",
                         disable_web_page_preview=True)


@router.message(Command("queue"))
async def cmd_queue(message: Message, session: AsyncSession):
    await show_queue(message, session, mode="p")


@router.message(Command("archive"))
async def cmd_archive(message: Message, session: AsyncSession):
    await show_queue(message, session, mode="a")


@router.callback_query(F.data.startswith("adm:"))
async def cb_admin(query: CallbackQuery, session: AsyncSession, state: FSMContext):
    parts = query.data.split(":")
    action, opp_id = parts[1], int(parts[2])
    mode = parts[3] if len(parts) > 3 else "p"
    opp = await session.get(Opportunity, opp_id)
    if opp is None:
        await query.answer("Gone")
        return

    if action == "skip":
        await query.answer()
        await show_queue(query.message, session, mode, after_id=opp_id, edit=True)
        return

    if action == "prev":
        await query.answer()
        await show_queue(query.message, session, mode, before_id=opp_id, edit=True)
        return

    if action == "archive":
        if mode == "p":
            opp.status = OppStatus.ARCHIVED
            session.add(AdminAction(admin_tg_id=query.from_user.id,
                                    opportunity_id=opp.id, action="archive"))
            await session.flush()
            await query.answer("Shelved — see /archive")
        else:
            opp.status = OppStatus.PENDING_REVIEW
            session.add(AdminAction(admin_tg_id=query.from_user.id,
                                    opportunity_id=opp.id, action="unarchive"))
            await session.flush()
            await query.answer("Moved back to /queue")
        await show_queue(query.message, session, mode, after_id=opp_id, edit=True)
        return

    if action == "reject":
        opp.status = OppStatus.REJECTED
        session.add(AdminAction(admin_tg_id=query.from_user.id, opportunity_id=opp.id,
                                action="reject"))
        await session.flush()
        await query.answer("Rejected")
        await show_queue(query.message, session, mode, after_id=opp_id, edit=True)
        return

    if action == "approve":
        # AI enrichment step: one call, capped daily, cached on the row.
        # On cap/failure -> publish immediately with the regex content (old path).
        await query.answer("✨ Enriching…" if not opp.enrichment else "Preview")
        enrichment = await enrich_opportunity(session, opp)
        if enrichment is None:
            await _publish_now(query, session, opp, mode, note="(no AI: cap/failure)")
            return
        preview = build_post_text(opp)
        preview_kb = kb([
            [("✅ Publish", f"adm:pub:{opp.id}:{mode}"),
             ("✏️ Edit first", f"adm:edit:{opp.id}:{mode}")],
            [("↩️ Publish original (no AI)", f"adm:orig:{opp.id}:{mode}")],
            [("◀️ Back to queue", f"adm:skip:{opp.id - 1}:{mode}")],
        ])
        if opp.image_file_id:
            await query.message.answer_photo(opp.image_file_id, caption=preview[:1024],
                                             parse_mode="HTML", reply_markup=preview_kb)
        else:
            await query.message.answer(preview[:4096], parse_mode="HTML",
                                       disable_web_page_preview=True,
                                       reply_markup=preview_kb)
        return

    if action == "pub":
        await _publish_now(query, session, opp, mode)
        return

    if action == "orig":
        opp.enrichment = None  # discard the AI version for this post
        await session.flush()
        await _publish_now(query, session, opp, mode, note="(original text)")
        return

    if action == "edit":
        await state.set_state(AdminEdit.waiting_text)
        await state.update_data(edit_opp_id=opp_id, edit_mode=mode)
        await query.answer()
        await query.message.answer(
            f"✏️ Editing #opp{opp_id}. Send the new post <b>body</b> text "
            "(HTML allowed). The Apply/Details/Analyze buttons and the #opp tag "
            "are auto-generated and cannot be edited. Send /cancel to abort.",
            parse_mode="HTML",
        )
        return

    if action == "photo":
        await state.set_state(AdminEdit.waiting_photo)
        await state.update_data(edit_opp_id=opp_id, edit_mode=mode)
        await query.answer()
        await query.message.answer(
            f"🖼 Send a photo to attach to #opp{opp_id} "
            "(it becomes the post image on publish), or /cancel.",
        )


@router.message(Command("cancel"), AdminEdit.waiting_text)
@router.message(Command("cancel"), AdminEdit.waiting_photo)
async def cancel_edit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.")


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
        "Body updated. Now send an <b>image</b> for the post, or /skip to keep "
        "the current one, or /cancel.", parse_mode="HTML",
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
    mode = data.get("edit_mode", "p")
    opp = await session.get(Opportunity, data["edit_opp_id"])
    await state.clear()
    if opp is None:
        return
    await message.answer("Preview of the post as it will publish:")
    preview = build_post_text(opp)[:4096]
    if opp.image_file_id:
        await message.answer_photo(opp.image_file_id, caption=preview[:1024],
                                   parse_mode="HTML")
    else:
        await message.answer(preview, parse_mode="HTML", disable_web_page_preview=True)
    await message.answer("Actions:", reply_markup=queue_kb(opp.id, mode))


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
        lines.append(f"• <b>{_esc(opp.title[:80])}</b>\n  ↳ <i>{_esc(opp.discard_reason or '')}</i>")
    await message.answer("\n".join(lines)[:4096], parse_mode="HTML",
                         disable_web_page_preview=True)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    counts = dict((await session.execute(
        select(Opportunity.status, func.count()).group_by(Opportunity.status)
    )).all())
    labels = [
        ("PENDING_REVIEW", "📥 pending"), ("ARCHIVED", "🗂 archived"),
        ("PUBLISHED", "📣 published"), ("APPROVED", "✅ approved"),
        ("REJECTED", "❌ rejected"), ("DISCARDED", "🗑 discarded"),
        ("EXPIRED", "⌛ expired"),
    ]
    lines = ["📊 <b>Pipeline stats</b>", ""]
    for status, label in labels:
        lines.append(f"{label}: <b>{counts.get(status, 0)}</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")
