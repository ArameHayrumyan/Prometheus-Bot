"""/start onboarding, deep links (opp_/fit_), /language, /profile, /help."""
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.details import build_detail_text
from app.bot.handlers.analyze import run_fit_analysis
from app.bot.keyboards import (degree_kb, english_test_kb, fields_kb,
                               language_kb, skip_kb)
from app.bot.states import Onboarding
from app.db.models import FieldTaxonomy, Opportunity, User
from app.db.settings_service import get_setting
from app.i18n import t

router = Router()


async def _taxonomy_names(session: AsyncSession) -> list[str]:
    rows = (await session.execute(
        select(FieldTaxonomy.name).where(FieldTaxonomy.active.is_(True))
    )).scalars().all()
    return list(rows)


async def _show_detail(message: Message, session: AsyncSession, user: User, opp_id: int) -> bool:
    opp = await session.get(Opportunity, opp_id)
    if opp is None:
        return False
    weights = await get_setting(session, "scoring_weights")
    await message.answer(build_detail_text(opp, user, weights),
                         parse_mode="HTML", disable_web_page_preview=True)
    return True


@router.message(CommandStart(deep_link=True))
async def start_deeplink(message: Message, command: CommandObject,
                         session: AsyncSession, user: User, state: FSMContext):
    payload = command.args or ""
    if payload.startswith("opp_") and payload[4:].isdigit():
        if await _show_detail(message, session, user, int(payload[4:])):
            return
    elif payload.startswith("fit_") and payload[4:].isdigit():
        opp = await session.get(Opportunity, int(payload[4:]))
        if opp is not None:
            await run_fit_analysis(message, session, user, opp)
            return
    await start_plain(message, session, user, state)


@router.message(CommandStart())
async def start_plain(message: Message, session: AsyncSession, user: User, state: FSMContext):
    if user.onboarded:
        await message.answer(t("help", user.language))
        return
    await message.answer(t("start_welcome", user.language))
    await message.answer(t("choose_language", user.language), reply_markup=language_kb())
    await state.set_state(Onboarding.language)


@router.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext, user: User):
    await message.answer(t("choose_language", user.language), reply_markup=language_kb())
    # no state: handled by the same lang: callback below, outside onboarding too


@router.callback_query(F.data.startswith("lang:"))
async def cb_language(query: CallbackQuery, session: AsyncSession,
                      user: User, state: FSMContext):
    user.language = query.data.split(":")[1]
    await query.answer()
    await query.message.edit_text(t("language_set", user.language))
    if await state.get_state() == Onboarding.language:
        await query.message.answer(t("choose_degree", user.language),
                                   reply_markup=degree_kb(user.language))
        await state.set_state(Onboarding.degree)


@router.callback_query(Onboarding.degree, F.data.startswith("deg:"))
async def cb_degree(query: CallbackQuery, session: AsyncSession,
                    user: User, state: FSMContext):
    user.degree_level_code = query.data.split(":")[1]
    names = await _taxonomy_names(session)
    await state.update_data(all_fields=names, selected=[])
    await query.answer()
    await query.message.edit_text(t("choose_fields", user.language),
                                  reply_markup=fields_kb(names, [], user.language))
    await state.set_state(Onboarding.fields)


@router.callback_query(Onboarding.fields, F.data.startswith("fld:"))
async def cb_fields(query: CallbackQuery, user: User, state: FSMContext):
    data = await state.get_data()
    all_fields: list[str] = data["all_fields"]
    selected: list[str] = data["selected"]
    arg = query.data.split(":")[1]
    if arg == "done":
        if not selected:
            await query.answer("⚠️", show_alert=False)
            return
        user.fields = selected
        await query.answer()
        await query.message.edit_text(t("ask_english_test", user.language),
                                      reply_markup=english_test_kb(user.language))
        await state.set_state(Onboarding.english_test)
        return
    name = all_fields[int(arg)]
    if name in selected:
        selected.remove(name)
    else:
        selected.append(name)
    await state.update_data(selected=selected)
    await query.answer()
    await query.message.edit_reply_markup(
        reply_markup=fields_kb(all_fields, selected, user.language))


@router.callback_query(Onboarding.english_test, F.data.startswith("eng:"))
async def cb_english_test(query: CallbackQuery, user: User, state: FSMContext):
    test = query.data.split(":")[1]
    await query.answer()
    if test == "none":
        user.english_test = None
        user.english_score = None
        user.english_expiry = None
        await query.message.edit_text(t("ask_gpa", user.language),
                                      reply_markup=skip_kb(user.language))
        await state.set_state(Onboarding.gpa)
        return
    user.english_test = test
    example = "7.0" if test == "IELTS" else "95"
    await query.message.edit_text(
        t("ask_english_score", user.language, test=test, example=example))
    await state.set_state(Onboarding.english_score)


@router.message(Onboarding.english_score)
async def msg_english_score(message: Message, user: User, state: FSMContext):
    try:
        score = float((message.text or "").replace(",", "."))
    except ValueError:
        await message.answer(t("invalid_number", user.language))
        return
    user.english_score = score
    await message.answer(t("ask_english_expiry", user.language))
    await state.set_state(Onboarding.english_expiry)


@router.message(Onboarding.english_expiry)
async def msg_english_expiry(message: Message, user: User, state: FSMContext):
    try:
        user.english_expiry = datetime.strptime((message.text or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        await message.answer(t("invalid_date", user.language))
        return
    await message.answer(t("ask_gpa", user.language), reply_markup=skip_kb(user.language))
    await state.set_state(Onboarding.gpa)


@router.callback_query(Onboarding.gpa, F.data == "skip")
async def cb_gpa_skip(query: CallbackQuery, user: User, state: FSMContext):
    await query.answer()
    await _finish(query.message, user, state)


@router.message(Onboarding.gpa)
async def msg_gpa(message: Message, user: User, state: FSMContext):
    try:
        gpa = float((message.text or "").replace(",", "."))
        if not 0 <= gpa <= 4.3:
            raise ValueError
    except ValueError:
        await message.answer(t("invalid_number", user.language))
        return
    user.gpa = gpa
    await _finish(message, user, state)


async def _finish(message: Message, user: User, state: FSMContext):
    user.onboarded = True
    await state.clear()
    await message.answer(t("onboarding_done", user.language))
    await message.answer(t("help", user.language))


@router.message(Command("help"))
async def cmd_help(message: Message, user: User):
    await message.answer(t("help", user.language))


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User):
    lang = user.language
    none = t("profile_none", lang)
    english = (f"{user.english_test} {user.english_score:g}"
               + (f" (→ {user.english_expiry})" if user.english_expiry else "")
               ) if user.english_test and user.english_score is not None else none
    lines = [
        f"<b>{t('profile_title', lang)}</b>",
        f"{t('profile_degree', lang)}: {user.degree_level_code or none}",
        f"{t('profile_fields', lang)}: {', '.join(user.fields or []) or none}",
        f"{t('profile_english', lang)}: {english}",
        f"{t('profile_gpa', lang)}: {user.gpa if user.gpa is not None else none}",
    ]
    from app.bot.keyboards import kb
    await message.answer("\n".join(lines), parse_mode="HTML",
                         reply_markup=kb([[(t("btn_edit_profile", lang), "redo_onboarding")]]))


@router.callback_query(F.data == "redo_onboarding")
async def cb_redo(query: CallbackQuery, user: User, state: FSMContext):
    user.onboarded = False
    await query.answer()
    await query.message.answer(t("choose_language", user.language),
                               reply_markup=language_kb())
    await state.set_state(Onboarding.language)
