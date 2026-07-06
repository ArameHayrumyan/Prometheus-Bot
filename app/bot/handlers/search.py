"""Menu-driven search (§10): tap-to-cycle filters, paginated results,
saved filters + notification toggles. Funding tier is NOT a filter here —
it's globally enforced by the hard gate.
"""
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import kb
from app.bot.posting import build_post_keyboard, build_post_text
from app.bot.states import SearchFlow
from app.constants import DEGREE_LEVELS, OpportunityType
from app.db.models import FieldTaxonomy, Opportunity, SavedFilter, User
from app.i18n import t

router = Router()

PAGE_SIZE = 5
DEADLINE_OPTS = [None, 7, 30, 90]
CHANCE_OPTS = [None, 20, 40, 60]
COUNTRY_OPTS = [None, "Armenia", "Germany", "USA", "UK", "Switzerland", "Remote", "EU"]
TYPE_OPTS = [None] + [str(v) for v in OpportunityType]
DEGREE_OPTS = [None] + list(DEGREE_LEVELS)


async def _field_opts(session: AsyncSession) -> list[str | None]:
    names = (await session.execute(
        select(FieldTaxonomy.name).where(FieldTaxonomy.active.is_(True))
    )).scalars().all()
    return [None] + list(names)


def _fmt(value, lang: str) -> str:
    return str(value) if value not in (None, "") else t("f_any", lang)


async def _menu(target: Message, session: AsyncSession, user: User,
                filters: dict, edit: bool) -> None:
    lang = user.language
    rows = [
        [(f"{t('f_field', lang)}: {_fmt(filters.get('field'), lang)}", "sf:field")],
        [(f"{t('f_degree', lang)}: {_fmt(filters.get('degree'), lang)}", "sf:degree")],
        [(f"{t('f_type', lang)}: {_fmt(filters.get('type'), lang)}", "sf:type")],
        [(f"{t('f_country', lang)}: {_fmt(filters.get('country'), lang)}", "sf:country")],
        [(f"{t('f_deadline', lang)}: "
          f"{_fmt(filters.get('deadline_days'), lang)}", "sf:deadline")],
        [(f"{t('f_minchance', lang)}: "
          f"{_fmt(filters.get('min_chance'), lang)}", "sf:minchance")],
        [(t("btn_run_search", lang), "sf:run")],
        [(t("btn_save_filter", lang), "sf:save")],
    ]
    text = t("search_title", lang)
    if edit:
        await target.edit_text(text, reply_markup=kb(rows))
    else:
        await target.answer(text, reply_markup=kb(rows))


@router.message(Command("search"))
async def cmd_search(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.update_data(sf={}, sf_page=0)
    await _menu(message, session, user, {}, edit=False)


def _cycle(options: list, current) -> object:
    try:
        idx = options.index(current)
    except ValueError:
        idx = 0
    return options[(idx + 1) % len(options)]


@router.callback_query(F.data.startswith("sf:"))
async def cb_search(query: CallbackQuery, session: AsyncSession,
                    user: User, state: FSMContext):
    action = query.data.split(":")[1]
    data = await state.get_data()
    filters: dict = data.get("sf", {})
    lang = user.language

    if action == "run":
        await query.answer()
        await _run_search(query.message, session, user, filters, page=0)
        return
    if action == "save":
        await query.answer()
        await query.message.answer(t("save_filter_prompt", lang))
        await state.set_state(SearchFlow.naming_filter)
        return

    if action == "field":
        filters["field"] = _cycle(await _field_opts(session), filters.get("field"))
    elif action == "degree":
        filters["degree"] = _cycle(DEGREE_OPTS, filters.get("degree"))
    elif action == "type":
        filters["type"] = _cycle(TYPE_OPTS, filters.get("type"))
    elif action == "country":
        filters["country"] = _cycle(COUNTRY_OPTS, filters.get("country"))
    elif action == "deadline":
        filters["deadline_days"] = _cycle(DEADLINE_OPTS, filters.get("deadline_days"))
    elif action == "minchance":
        filters["min_chance"] = _cycle(CHANCE_OPTS, filters.get("min_chance"))
    filters = {k: v for k, v in filters.items() if v is not None}
    await state.update_data(sf=filters)
    await query.answer()
    await _menu(query.message, session, user, filters, edit=True)


def build_query(filters: dict):
    stmt = select(Opportunity).where(Opportunity.status == "PUBLISHED")
    if f := filters.get("field"):
        stmt = stmt.where(Opportunity.fields.contains([f]))
    if d := filters.get("degree"):
        stmt = stmt.where(Opportunity.degree_levels.contains([d]))
    if ot := filters.get("type"):
        stmt = stmt.where(Opportunity.opportunity_type == ot)
    if c := filters.get("country"):
        stmt = stmt.where(Opportunity.country.ilike(f"%{c}%"))
    if dd := filters.get("deadline_days"):
        cutoff = date.today() + timedelta(days=int(dd))
        stmt = stmt.where(Opportunity.deadline.is_not(None), Opportunity.deadline <= cutoff,
                          Opportunity.deadline >= date.today())
    if mc := filters.get("min_chance"):
        stmt = stmt.where(Opportunity.chance_percent >= int(mc))
    return stmt.order_by(Opportunity.published_at.desc())


async def _run_search(message: Message, session: AsyncSession, user: User,
                      filters: dict, page: int) -> None:
    lang = user.language
    stmt = build_query(filters).offset(page * PAGE_SIZE).limit(PAGE_SIZE + 1)
    opps = list((await session.execute(stmt)).scalars().all())
    if not opps and page == 0:
        await message.answer(t("search_no_results", lang))
        return
    has_next = len(opps) > PAGE_SIZE
    me = await message.bot.get_me()
    for opp in opps[:PAGE_SIZE]:
        await message.answer(
            build_post_text(opp, lang)[:4096],
            reply_markup=build_post_keyboard(opp, me.username or "", lang,
                                             save_as_callback=True),
            parse_mode="HTML", disable_web_page_preview=True,
        )
    nav: list[tuple[str, str]] = []
    if page > 0:
        nav.append((t("prev_page", lang), f"sfpage:{page - 1}"))
    if has_next:
        nav.append((t("next_page", lang), f"sfpage:{page + 1}"))
    if nav:
        await message.answer(f"— {page + 1} —", reply_markup=kb([nav]))


@router.callback_query(F.data.startswith("sfpage:"))
async def cb_page(query: CallbackQuery, session: AsyncSession,
                  user: User, state: FSMContext):
    page = int(query.data.split(":")[1])
    filters = (await state.get_data()).get("sf", {})
    await query.answer()
    await _run_search(query.message, session, user, filters, page)


@router.message(SearchFlow.naming_filter)
async def msg_filter_name(message: Message, session: AsyncSession,
                          user: User, state: FSMContext):
    filters = (await state.get_data()).get("sf", {})
    session.add(SavedFilter(user_tg_id=user.tg_id,
                            name=(message.text or "filter")[:100],
                            filters=filters, notify=True))
    await session.flush()
    await state.set_state(None)
    await message.answer(t("filter_saved", user.language))


@router.message(Command("filters"))
async def cmd_filters(message: Message, session: AsyncSession, user: User):
    await _filters_menu(message, session, user, edit=False)


async def _filters_menu(message: Message, session: AsyncSession, user: User, edit: bool):
    lang = user.language
    saved = (await session.execute(
        select(SavedFilter).where(SavedFilter.user_tg_id == user.tg_id)
    )).scalars().all()
    if not saved:
        await message.answer(t("filters_empty", lang))
        return
    rows = []
    for sf in saved:
        bell = t("btn_notify_on", lang) if sf.notify else t("btn_notify_off", lang)
        rows.append([
            (f"▶️ {sf.name[:20]}", f"runflt:{sf.id}"),
            (bell, f"toggleflt:{sf.id}"),
            ("🗑", f"delflt:{sf.id}"),
        ])
    text = t("filters_title", lang)
    if edit:
        await message.edit_text(text, reply_markup=kb(rows))
    else:
        await message.answer(text, reply_markup=kb(rows))


@router.callback_query(F.data.startswith("runflt:"))
async def cb_run_filter(query: CallbackQuery, session: AsyncSession,
                        user: User, state: FSMContext):
    sf = await session.get(SavedFilter, int(query.data.split(":")[1]))
    await query.answer()
    if sf is None or sf.user_tg_id != user.tg_id:
        return
    await state.update_data(sf=sf.filters or {})
    await _run_search(query.message, session, user, sf.filters or {}, page=0)


@router.callback_query(F.data.startswith("toggleflt:"))
async def cb_toggle_filter(query: CallbackQuery, session: AsyncSession, user: User):
    sf = await session.get(SavedFilter, int(query.data.split(":")[1]))
    if sf is not None and sf.user_tg_id == user.tg_id:
        sf.notify = not sf.notify
        await session.flush()
    await query.answer()
    await _filters_menu(query.message, session, user, edit=True)


@router.callback_query(F.data.startswith("delflt:"))
async def cb_del_filter(query: CallbackQuery, session: AsyncSession, user: User):
    sf = await session.get(SavedFilter, int(query.data.split(":")[1]))
    if sf is not None and sf.user_tg_id == user.tg_id:
        await session.delete(sf)
        await session.flush()
    await query.answer(t("filter_deleted", user.language))
    await _filters_menu(query.message, session, user, edit=True)
