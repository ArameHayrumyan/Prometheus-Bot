"""Admin review queue (§9): audience tabs (student/youth), list filters
(type / field / eligibility), classic card with approve / reject / edit /
photo / archive, prev-next navigation, AI-enrichment preview with a
channel picker (incl. free channels and forum topics) and a per-post
language toggle. Also the digest approval callbacks.

Callback formats:
  adm:<action>:<opp_id>:<mode>              card actions (mode p|a)
  ql:<mode>:<page>                          list pagination
  qf:<dim>                                  cycle a list filter (FSM-stored)
  admch:<opp>:<mode>:<lang>:<csv>:<cid>     toggle channel cid in the picker
  admlg:<opp>:<mode>:<lang>:<csv>           cycle post language en<->hy
  admpub:<opp>:<mode>:<lang>:<csv>          publish to selected channels
  dg:<post|skip>:<degree_code>              digest approval
"""
import html

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.enrich import enrich_opportunity
from app.bot.handlers.admin import IsAdmin
from app.bot.keyboards import kb
from app.bot.posting import (FUNDING_LABEL, all_channels, build_post_text,
                             channel_label, default_channel_ids,
                             notify_saved_filters, publish_opportunity,
                             type_label)
from app.bot.states import AdminEdit
from app.constants import OppStatus, OpportunityType
from app.db.models import AdminAction, FieldTaxonomy, Opportunity
from app.logging_setup import get_logger
from app.utils.text import smart_truncate

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
log = get_logger("bot.admin.queue")

MODE_STATUS = {"p": OppStatus.PENDING_REVIEW, "a": OppStatus.ARCHIVED}
MODE_TITLE = {"p": "📥 Review queue", "a": "🗂 Archive"}
LIST_PAGE = 10
TYPE_CYCLE = [None] + [str(v) for v in OpportunityType]
ELIG_CYCLE = [None, "uncertain", "clear"]


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


# ------------------------------------------------------------- filters ------

async def get_qf(state: FSMContext) -> dict:
    data = await state.get_data()
    qf = data.get("adminqf") or {}
    qf.setdefault("aud", "student")
    return qf


async def set_qf(state: FSMContext, qf: dict) -> None:
    await state.update_data(adminqf=qf)


def filter_clauses(qf: dict) -> list:
    clauses = [Opportunity.audience == qf.get("aud", "student")]
    if qf.get("type"):
        clauses.append(Opportunity.opportunity_type == qf["type"])
    if qf.get("field"):
        clauses.append(Opportunity.fields.contains([qf["field"]]))
    if qf.get("elig") == "uncertain":
        clauses.append(Opportunity.armenian_eligibility == "UNCERTAIN")
    elif qf.get("elig") == "clear":
        clauses.append(Opportunity.armenian_eligibility != "UNCERTAIN")
    return clauses


def _cycle(options: list, current):
    try:
        idx = options.index(current)
    except ValueError:
        idx = 0
    return options[(idx + 1) % len(options)]


# ---------------------------------------------------------------- card ------

def queue_card(opp: Opportunity, total: int, mode: str) -> str:
    aud = "  ·  🌱 YOUTH" if opp.audience == "youth" else ""
    lines = [
        f"{MODE_TITLE[mode]} · <b>{total}</b> item{'s' if total != 1 else ''}",
        f"<b>{type_label(opp.opportunity_type)}</b>  ·  #opp{opp.id}{aud}",
        "",
        f"<b>{_esc(opp.title)}</b>",
    ]
    if opp.org:
        lines.append(f"🏛 <i>{_esc(opp.org)}</i>")
    lines.append("")
    lines.append(f"<blockquote expandable>{_esc(smart_truncate(opp.description, 1500))}</blockquote>")
    lines.append("")
    lines.extend([
        f"💰 {FUNDING_LABEL.get(opp.funding_tier, opp.funding_tier)}",
        f"📅 {opp.deadline or 'no deadline stated'}   ⏱ {f'{opp.duration_days}d' if opp.duration_days else '—'}",
        f"🎓 {', '.join(opp.degree_levels or []) or '—'}",
        f"🔬 {', '.join(opp.fields or []) or '—'}",
        f"⚖️ legitimacy <b>{opp.legitimacy_score}</b>/100   🎯 chance ~<b>{opp.chance_percent}%</b>",
        f"🔗 {_esc(opp.url)}",
    ])
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
        [("📋 List view", f"ql:{mode}:cur")],
    ])


async def _count(session: AsyncSession, mode: str, qf: dict) -> int:
    return (await session.execute(
        select(func.count()).select_from(Opportunity)
        .where(Opportunity.status == MODE_STATUS[mode], *filter_clauses(qf))
    )).scalar_one()


async def _fetch_item(session: AsyncSession, mode: str, qf: dict,
                      after_id: int = 0,
                      before_id: int | None = None) -> Opportunity | None:
    status = MODE_STATUS[mode]
    if before_id is not None:
        stmt = (select(Opportunity)
                .where(Opportunity.status == status, Opportunity.id < before_id,
                       *filter_clauses(qf))
                .order_by(Opportunity.id.desc()).limit(1))
    else:
        stmt = (select(Opportunity)
                .where(Opportunity.status == status, Opportunity.id > after_id,
                       *filter_clauses(qf))
                .order_by(Opportunity.id).limit(1))
    return (await session.execute(stmt)).scalar_one_or_none()


async def show_queue(message: Message, session: AsyncSession, mode: str = "p",
                     qf: dict | None = None, after_id: int = 0,
                     before_id: int | None = None, edit: bool = False):
    qf = qf or {"aud": "student"}
    total = await _count(session, mode, qf)
    opp = await _fetch_item(session, mode, qf, after_id, before_id)
    if opp is None and (after_id or before_id is not None):
        opp = await _fetch_item(session, mode, qf, 0, None)  # wrap around
    if opp is None:
        text = ("📭 Nothing here with the current filters "
                f"(audience: {qf.get('aud')}). /queue resets to the list.")
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
            pass  # previous message was a photo preview -> send fresh
    await message.answer(text, reply_markup=markup, parse_mode="HTML",
                         disable_web_page_preview=True)


# ------------------------------------------------------------ list view -----

async def show_list(message: Message, session: AsyncSession, state: FSMContext,
                    mode: str = "p", page: int = 0, edit: bool = False):
    qf = await get_qf(state)
    total = await _count(session, mode, qf)
    aud_icon = "🌱" if qf["aud"] == "youth" else "🎓"
    filter_row = [
        (f"{aud_icon} {qf['aud']}", "qf:aud"),
        (f"🏷 {qf.get('type') or 'any'}", "qf:type"),
        (f"🔬 {(qf.get('field') or 'any')[:12]}", "qf:field"),
        ({"uncertain": "⚠️ only", "clear": "✅ clear"}.get(qf.get("elig"), "⚪ any"),
         "qf:elig"),
    ]
    if total == 0:
        text = (f"{MODE_TITLE[mode]} — empty for these filters\n"
                f"👥 {qf['aud']} · 🏷 {qf.get('type') or 'any'} · "
                f"🔬 {qf.get('field') or 'any'} · {qf.get('elig') or 'any'}")
        markup = kb([filter_row])
        if edit:
            try:
                await message.edit_text(text, reply_markup=markup)
                return
            except Exception:
                pass
        await message.answer(text, reply_markup=markup)
        return
    items = (await session.execute(
        select(Opportunity)
        .where(Opportunity.status == MODE_STATUS[mode], *filter_clauses(qf))
        .order_by(Opportunity.id)
        .offset(page * LIST_PAGE)
        .limit(LIST_PAGE)
    )).scalars().all()
    pages = (total + LIST_PAGE - 1) // LIST_PAGE
    lines = [f"{MODE_TITLE[mode]} · <b>{total}</b> items · page {page + 1}/{pages}", ""]
    number_buttons: list[tuple[str, str]] = []
    for i, opp in enumerate(items, 1):
        flags = " ⚠️" if opp.armenian_eligibility == "UNCERTAIN" else ""
        lines.append(f"<b>{i}.</b> {type_label(opp.opportunity_type)} — "
                     f"{_esc(opp.title[:60])}{flags}")
        number_buttons.append((str(i), f"adm:open:{opp.id}:{mode}"))
    rows = [filter_row]
    rows += [number_buttons[i:i + 5] for i in range(0, len(number_buttons), 5)]
    nav: list[tuple[str, str]] = []
    if page > 0:
        nav.append(("◀️", f"ql:{mode}:{page - 1}"))
    nav.append(("🃏 Card view", f"adm:open:{items[0].id}:{mode}"))
    if (page + 1) * LIST_PAGE < total:
        nav.append(("▶️", f"ql:{mode}:{page + 1}"))
    rows.append(nav)
    await state.update_data(list_page=page)  # remember for card -> list return
    text = "\n".join(lines)[:4096]
    markup = kb(rows)
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.message(Command("queue"))
async def cmd_queue(message: Message, command: CommandObject,
                    session: AsyncSession, state: FSMContext):
    qf = await get_qf(state)
    arg = (command.args or "").strip().lower()
    if arg in ("youth", "student"):
        qf["aud"] = arg
        await set_qf(state, qf)
    await state.update_data(adminmode="p")
    await show_list(message, session, state, mode="p")


@router.message(Command("archive"))
async def cmd_archive(message: Message, session: AsyncSession, state: FSMContext):
    await state.update_data(adminmode="a")
    await show_list(message, session, state, mode="a")


@router.callback_query(F.data.startswith("ql:"))
async def cb_queue_list_page(query: CallbackQuery, session: AsyncSession,
                             state: FSMContext):
    _, mode, page = query.data.split(":")
    if page == "cur":  # returning from a card -> the page it was opened from
        page = (await state.get_data()).get("list_page", 0)
    await query.answer()
    await state.update_data(adminmode=mode)
    await show_list(query.message, session, state, mode=mode, page=int(page), edit=True)


@router.callback_query(F.data.startswith("qf:"))
async def cb_queue_filter(query: CallbackQuery, session: AsyncSession,
                          state: FSMContext):
    dim = query.data.split(":")[1]
    qf = await get_qf(state)
    if dim == "aud":
        qf["aud"] = "youth" if qf["aud"] == "student" else "student"
    elif dim == "type":
        qf["type"] = _cycle(TYPE_CYCLE, qf.get("type"))
    elif dim == "field":
        names = list((await session.execute(
            select(FieldTaxonomy.name).where(FieldTaxonomy.active.is_(True))
        )).scalars().all())
        qf["field"] = _cycle([None] + names, qf.get("field"))
    elif dim == "elig":
        qf["elig"] = _cycle(ELIG_CYCLE, qf.get("elig"))
    qf = {k: v for k, v in qf.items() if v is not None}
    qf.setdefault("aud", "student")
    await set_qf(state, qf)
    mode = (await state.get_data()).get("adminmode", "p")
    await query.answer()
    await show_list(query.message, session, state, mode=mode, page=0, edit=True)


# -------------------------------------------- preview & channel picker ------

def _parse_csv(csv: str) -> set[int]:
    return {int(x) for x in csv.split(",") if x and x != "0"}


def _to_csv(ids: set[int]) -> str:
    return ",".join(str(i) for i in sorted(ids)) or "0"


def preview_kb(opp: Opportunity, mode: str, lang: str, selected: set[int],
               channels: list) -> object:
    csv = _to_csv(selected)
    toggle_buttons = [
        (("✅ " if c.id in selected else "⬜ ") + channel_label(c)[:14],
         f"admch:{opp.id}:{mode}:{lang}:{csv}:{c.id}")
        for c in channels
    ]
    rows = [toggle_buttons[i:i + 3] for i in range(0, len(toggle_buttons), 3)]
    rows.append([(f"🌐 Post language: {lang.upper()} (tap to switch)",
                  f"admlg:{opp.id}:{mode}:{lang}:{csv}")])
    rows.append([("🚀 Publish to selected", f"admpub:{opp.id}:{mode}:{lang}:{csv}"),
                 ("✏️ Edit first", f"adm:edit:{opp.id}:{mode}")])
    if opp.enrichment:
        rows.append([("↩️ Use original (no AI)", f"adm:orig:{opp.id}:{mode}")])
    # reopen THIS item's card (not skip-to-next, which could land elsewhere
    # once filters are applied)
    rows.append([("◀️ Back to this item", f"adm:open:{opp.id}:{mode}")])
    return kb(rows)


async def _send_preview(message: Message, session: AsyncSession, opp: Opportunity,
                        mode: str, note: str = "", replace: bool = False,
                        lang: str | None = None,
                        selected: set[int] | None = None) -> None:
    channels = await all_channels(session)
    if not channels:
        await message.answer("⚠️ No channels configured — check CHANNEL_ID_* env "
                             "vars or /addchannel.")
        return
    if selected is None:
        selected = default_channel_ids(opp, channels)
    if lang is None:
        lang = "hy" if opp.audience == "youth" else "en"
    text = (note + build_post_text(opp, lang))[:4096]
    markup = preview_kb(opp, mode, lang, selected, channels)
    if replace:
        try:
            await message.edit_text(text, parse_mode="HTML",
                                    disable_web_page_preview=True, reply_markup=markup)
            return
        except Exception:
            try:
                await message.edit_caption(caption=text[:1024], parse_mode="HTML",
                                           reply_markup=markup)
                return
            except Exception:
                pass
    if opp.image_file_id:
        await message.answer_photo(opp.image_file_id, caption=text[:1024],
                                   parse_mode="HTML", reply_markup=markup)
    else:
        await message.answer(text, parse_mode="HTML",
                             disable_web_page_preview=True, reply_markup=markup)


@router.callback_query(F.data.startswith("admch:"))
async def cb_channel_toggle(query: CallbackQuery, session: AsyncSession):
    _, opp_id, mode, lang, csv, cid = query.data.split(":")
    opp = await session.get(Opportunity, int(opp_id))
    await query.answer()
    if opp is None:
        return
    selected = _parse_csv(csv) ^ {int(cid)}
    channels = await all_channels(session)
    try:
        await query.message.edit_reply_markup(
            reply_markup=preview_kb(opp, mode, lang, selected, channels))
    except Exception:
        pass


@router.callback_query(F.data.startswith("admlg:"))
async def cb_lang_toggle(query: CallbackQuery, session: AsyncSession):
    _, opp_id, mode, lang, csv = query.data.split(":")
    opp = await session.get(Opportunity, int(opp_id))
    await query.answer()
    if opp is None:
        return
    new_lang = "hy" if lang == "en" else "en"
    await _send_preview(query.message, session, opp, mode, replace=True,
                        lang=new_lang, selected=_parse_csv(csv))


@router.callback_query(F.data.startswith("admpub:"))
async def cb_publish(query: CallbackQuery, session: AsyncSession, state: FSMContext):
    _, opp_id, mode, lang, csv = query.data.split(":")
    selected = _parse_csv(csv)
    if not selected:
        await query.answer("Select at least one channel first", show_alert=True)
        return
    opp = await session.get(Opportunity, int(opp_id))
    if opp is None:
        await query.answer("Gone")
        return
    await _publish_now(query, session, state, opp, mode,
                       channel_ids=sorted(selected), lang=lang)


async def _publish_now(query: CallbackQuery, session: AsyncSession,
                       state: FSMContext, opp: Opportunity, mode: str,
                       channel_ids: list[int], lang: str, note: str = "") -> None:
    session.add(AdminAction(admin_tg_id=query.from_user.id, opportunity_id=opp.id,
                            action="approve",
                            payload={"channels": channel_ids, "lang": lang}))
    opp.status = OppStatus.APPROVED
    posted = await publish_opportunity(query.bot, session, opp, channel_ids, lang)
    # COMMIT NOW: the channel post is already sent (an irreversible side effect).
    # Any later failure (stale callback answer, edit error, network blip) must
    # NOT roll back the PUBLISHED status / ChannelPost rows, or the post would
    # exist in the channel while /search and forward-matching stay broken.
    await session.commit()
    try:
        await query.answer(f"Published to {posted} channel(s) {note}".strip())
    except Exception:
        pass
    try:
        if posted:
            await notify_saved_filters(query.bot, session, opp)
        qf = await get_qf(state)
        await show_queue(query.message, session, mode, qf, after_id=opp.id, edit=True)
    except Exception as e:
        log.warning("post_publish_side_effect_failed", opp_id=opp.id, error=str(e)[:200])


# -------------------------------------------------------- card actions ------

@router.callback_query(F.data.startswith("adm:"))
async def cb_admin(query: CallbackQuery, session: AsyncSession, state: FSMContext):
    parts = query.data.split(":")
    action, opp_id = parts[1], int(parts[2])
    mode = parts[3] if len(parts) > 3 else "p"
    qf = await get_qf(state)
    opp = await session.get(Opportunity, opp_id)
    if opp is None:
        await query.answer("Gone")
        return

    if action == "open":
        await query.answer()
        # opening from the list: card must match the item regardless of filters
        qf_open = dict(qf, aud=opp.audience)
        await set_qf(state, qf_open)
        await show_queue(query.message, session, mode, qf_open,
                         after_id=opp_id - 1, edit=True)
        return

    if action == "skip":
        await query.answer()
        await show_queue(query.message, session, mode, qf, after_id=opp_id, edit=True)
        return

    if action == "prev":
        await query.answer()
        await show_queue(query.message, session, mode, qf, before_id=opp_id, edit=True)
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
        await show_queue(query.message, session, mode, qf, after_id=opp_id, edit=True)
        return

    if action == "reject":
        opp.status = OppStatus.REJECTED
        session.add(AdminAction(admin_tg_id=query.from_user.id, opportunity_id=opp.id,
                                action="reject"))
        await session.flush()
        await query.answer("Rejected")
        await show_queue(query.message, session, mode, qf, after_id=opp_id, edit=True)
        return

    if action == "approve":
        # AI enrichment (one capped call, cached). Whether or not it succeeds,
        # NOTHING publishes without the explicit 🚀 tap in the preview.
        await query.answer("✨ Enriching…" if not opp.enrichment else "Preview")
        enrichment = await enrich_opportunity(session, opp)
        note = "" if enrichment else "⚠️ AI unavailable (cap/failure) — original text.\n"
        await _send_preview(query.message, session, opp, mode, note=note)
        return

    if action == "orig":
        opp.enrichment = None  # discard the AI version; preview the original
        await session.flush()
        await query.answer("AI version discarded")
        await _send_preview(query.message, session, opp, mode, replace=True)
        return

    if action == "edit":
        await state.set_state(AdminEdit.waiting_text)
        await state.update_data(edit_opp_id=opp_id, edit_mode=mode)
        await query.answer()
        await query.message.answer(
            f"✏️ Editing #opp{opp_id}. Send the new post <b>body</b> text "
            "(HTML allowed). Buttons and the #opp tag are auto-generated and "
            "cannot be edited. Send /cancel to abort.",
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
    await state.set_state(None)
    await message.answer("Cancelled.")


@router.message(AdminEdit.waiting_text)
async def edit_text(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    opp = await session.get(Opportunity, data["edit_opp_id"])
    if opp is None:
        await state.set_state(None)
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
    await state.set_state(None)
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


# --------------------------------------------------- digest / stats etc -----

@router.message(Command("digest"))
async def cmd_digest(message: Message, session: AsyncSession):
    """Compile digest previews on demand (same as the Sunday job)."""
    from app.scheduler.jobs import weekly_digest

    await message.answer("🗓 Compiling digest previews…")
    await weekly_digest(message.bot)


@router.callback_query(F.data.startswith("dg:"))
async def cb_digest(query: CallbackQuery, session: AsyncSession):
    from datetime import date

    from app.db.models import Channel
    from app.scheduler.jobs import build_digest_text

    _, action, channel_id = query.data.split(":")
    if action == "skip":
        await query.answer("Skipped this week")
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    channel = await session.get(Channel, int(channel_id))
    if channel is None:
        await query.answer("Channel not configured")
        return
    me = await query.bot.get_me()
    # rebuild at post time so the digest reflects the current state
    text = await build_digest_text(session, me.username or "", date.today())
    if text is None:
        await query.answer("Not enough open items anymore", show_alert=True)
        return
    try:
        await query.bot.send_message(channel.tg_channel_id, text, parse_mode="HTML",
                                     disable_web_page_preview=True,
                                     message_thread_id=channel.thread_id)
    except Exception as e:
        await query.answer(f"Failed: {str(e)[:150]}", show_alert=True)
        return
    session.add(AdminAction(admin_tg_id=query.from_user.id, action="digest_post",
                            payload={"channel_id": channel.id}))
    await query.answer("📣 Posted")
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


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
        aud = "🌱 " if opp.audience == "youth" else ""
        lines.append(f"• {aud}<b>{_esc(opp.title[:80])}</b>\n  ↳ <i>{_esc(opp.discard_reason or '')}</i>")
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
    youth_pending = (await session.execute(
        select(func.count()).select_from(Opportunity)
        .where(Opportunity.status == OppStatus.PENDING_REVIEW,
               Opportunity.audience == "youth")
    )).scalar_one()
    lines.append(f"   of pending: 🌱 youth <b>{youth_pending}</b>")

    from app.db.models import SavedOpportunity, User
    users_total = (await session.execute(
        select(func.count()).select_from(User))).scalar_one()
    onboarded = (await session.execute(
        select(func.count()).select_from(User).where(User.onboarded.is_(True)))).scalar_one()
    saves = (await session.execute(
        select(func.count()).select_from(SavedOpportunity))).scalar_one()
    applied = (await session.execute(
        select(func.count()).select_from(SavedOpportunity)
        .where(SavedOpportunity.applied_at.is_not(None)))).scalar_one()
    outcomes = dict((await session.execute(
        select(SavedOpportunity.outcome, func.count())
        .where(SavedOpportunity.outcome.is_not(None))
        .group_by(SavedOpportunity.outcome))).all())
    lines += [
        "",
        "👥 <b>Users</b>",
        f"total: <b>{users_total}</b> (onboarded: {onboarded})",
        f"⭐ saves: <b>{saves}</b> · ✅ applied: <b>{applied}</b>",
        f"outcomes — 🎉 {outcomes.get('accepted', 0)} accepted, "
        f"😞 {outcomes.get('rejected', 0)} rejected",
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")
