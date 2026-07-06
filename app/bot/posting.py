"""Channel post rendering + publishing.

The free-editable body (edited_text) and the auto-generated template parts
(header/footer/#opp tag/buttons) are strictly separated: admins can only
replace the body; buttons and the #opp reference are always regenerated.
"""
import html

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import OppStatus
from app.db.models import Channel, ChannelPost, Opportunity, SavedFilter, User
from app.i18n import t
from app.logging_setup import get_logger
from app.utils.text import smart_truncate

log = get_logger("bot.posting")

TYPE_EMOJI = {
    "internship": "🧑‍💻", "scholarship": "🎓", "fellowship": "🔬",
    "training": "📚", "job": "💼", "hackathon": "🏆",
}

# Compact English labels used on admin cards (student posts use i18n keys)
FUNDING_LABEL = {
    "FULLY_FUNDED": "Fully funded",
    "MOSTLY_FUNDED_ACCEPTABLE": "Mostly funded",
    "STUDENT_PAYS": "Student pays",
    "UNKNOWN": "Funding unclear",
}

DEGREE_TAG = {"undergrad": "#undergrad", "masters": "#masters", "phd": "#phd"}


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def default_body(opp: Opportunity) -> str:
    lines = [f"<b>{_esc(opp.title)}</b>"]
    if opp.org:
        lines.append(f"🏛 <i>{_esc(opp.org)}</i>")
    desc = smart_truncate(opp.description, 900)
    if desc:
        lines.append("")
        lines.append(f"<blockquote expandable>{_esc(desc)}</blockquote>")
    return "\n".join(lines)


def build_post_text(opp: Opportunity, lang: str = "en") -> str:
    emoji = TYPE_EMOJI.get(opp.opportunity_type, "✨")
    header = f"{emoji} <b>{opp.opportunity_type.upper()}</b>"
    if opp.country:
        header += f"  ·  🌍 {_esc(opp.country)}"

    enr = opp.enrichment or {}
    # body precedence: admin free-edit > AI tl;dr > scraped description
    if opp.edited_text:
        body = opp.edited_text
    elif enr.get("tldr"):
        lines = [f"<b>{_esc(opp.title)}</b>"]
        if opp.org:
            lines.append(f"🏛 <i>{_esc(opp.org)}</i>")
        lines.append("")
        lines.append(_esc(enr["tldr"]))
        body = "\n".join(lines)
    else:
        body = default_body(opp)
    if enr.get("requirements"):
        body += "\n\n📋 <b>{}</b>\n".format(t("detail_requirements", lang))
        body += "\n".join(f"• {_esc(b)}" for b in enr["requirements"])
    if enr.get("competitiveness"):
        body += f"\n\n📊 <i>{_esc(enr['competitiveness'])}</i>"

    facts = []
    facts.append(f"💰 <b>{t('funding_' + opp.funding_tier, lang)}</b>")
    deadline = opp.deadline.isoformat() if opp.deadline else t("no_deadline", lang)
    facts.append(f"📅 {t('detail_deadline', lang)}: <b>{deadline}</b>")
    if opp.fields:
        facts.append(f"🔬 {_esc(' · '.join(opp.fields))}")
    if opp.english_req_score is not None:
        facts.append(t("english_req", lang,
                       req=f"{opp.english_req_test} {opp.english_req_score:g}"))
    facts.append(f"🎯 {t('detail_chance', lang)}: <b>~{opp.chance_percent}%</b>")
    if opp.armenian_eligibility in ("ELIGIBLE", "UNCERTAIN"):
        facts.append(t("eligibility_" + opp.armenian_eligibility, lang))

    tags = [f"#opp{opp.id}", f"#{opp.opportunity_type}"]
    tags += [DEGREE_TAG[d] for d in (opp.degree_levels or []) if d in DEGREE_TAG]
    footer = f"<i>{' '.join(tags)}</i>"
    return "\n\n".join([header, body, "\n".join(facts), footer])


def build_post_keyboard(opp: Opportunity, bot_username: str, lang: str = "en",
                        save_as_callback: bool = False) -> InlineKeyboardMarkup:
    """Channel posts use a Save deep-link (channel buttons are shared by all
    subscribers); DM cards use a Save callback (save_as_callback=True)."""
    save_btn = (
        InlineKeyboardButton(text=t("btn_save", lang), callback_data=f"sv:{opp.id}")
        if save_as_callback else
        InlineKeyboardButton(text=t("btn_save", lang),
                             url=f"https://t.me/{bot_username}?start=save_{opp.id}")
    )
    rows = [
        [InlineKeyboardButton(text=t("btn_apply", lang), url=opp.apply_url or opp.url),
         save_btn],
        [InlineKeyboardButton(text=t("btn_details", lang),
                              url=f"https://t.me/{bot_username}?start=opp_{opp.id}"),
         InlineKeyboardButton(text=t("btn_analyze", lang),
                              url=f"https://t.me/{bot_username}?start=fit_{opp.id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def publish_opportunity(bot: Bot, session: AsyncSession, opp: Opportunity) -> int:
    """Post to every channel matching the opportunity's degree levels.
    Returns the number of channels posted to."""
    me = await bot.get_me()
    text = build_post_text(opp)
    keyboard = build_post_keyboard(opp, me.username or "")
    channels = (await session.execute(
        select(Channel).where(Channel.degree_level_code.in_(opp.degree_levels or []))
    )).scalars().all()

    posted = 0
    for channel in channels:
        try:
            if opp.image_file_id:
                msg = await bot.send_photo(
                    channel.tg_channel_id, opp.image_file_id,
                    caption=text[:1024], reply_markup=keyboard, parse_mode="HTML",
                )
            else:
                msg = await bot.send_message(
                    channel.tg_channel_id, text[:4096],
                    reply_markup=keyboard, parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            session.add(ChannelPost(
                opportunity_id=opp.id,
                tg_channel_id=channel.tg_channel_id,
                message_id=msg.message_id,
            ))
            posted += 1
        except Exception as e:
            log.error("publish_failed", opp_id=opp.id,
                      channel=channel.tg_channel_id, error=str(e)[:300])
    if posted:
        opp.status = OppStatus.PUBLISHED
        from app.db.models import utcnow
        opp.published_at = utcnow()
    return posted


def filter_matches(filters: dict, opp: Opportunity) -> bool:
    if (f := filters.get("field")) and f not in (opp.fields or []):
        return False
    if (d := filters.get("degree")) and d not in (opp.degree_levels or []):
        return False
    if (ot := filters.get("type")) and ot != opp.opportunity_type:
        return False
    if (c := filters.get("country")) and c.lower() not in (opp.country or "").lower():
        return False
    if (mc := filters.get("min_chance")) and opp.chance_percent < int(mc):
        return False
    return True


async def notify_saved_filters(bot: Bot, session: AsyncSession, opp: Opportunity) -> None:
    """DM users whose notify-enabled saved filters match a newly published post."""
    rows = (await session.execute(
        select(SavedFilter, User)
        .join(User, User.tg_id == SavedFilter.user_tg_id)
        .where(SavedFilter.notify.is_(True))
    )).all()
    me = await bot.get_me()
    notified: set[int] = set()
    for saved, user in rows:
        if user.tg_id in notified or not filter_matches(saved.filters or {}, opp):
            continue
        try:
            await bot.send_message(
                user.tg_id,
                t("new_match_notification", user.language, name=saved.name)
                + "\n\n" + build_post_text(opp, user.language)[:3500],
                reply_markup=build_post_keyboard(opp, me.username or "", user.language),
                parse_mode="HTML", disable_web_page_preview=True,
            )
            notified.add(user.tg_id)
        except Exception as e:
            log.info("notify_failed", user=user.tg_id, error=str(e)[:150])
