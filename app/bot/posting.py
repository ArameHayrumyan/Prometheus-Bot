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

log = get_logger("bot.posting")

TYPE_EMOJI = {
    "internship": "🧑‍💻", "scholarship": "🎓", "fellowship": "🔬",
    "training": "📚", "job": "💼", "hackathon": "🏆",
}


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def default_body(opp: Opportunity) -> str:
    lines = [f"<b>{_esc(opp.title)}</b>"]
    if opp.org:
        lines.append(f"🏛 {_esc(opp.org)}")
    lines.append("")
    desc = opp.description[:600]
    if len(opp.description) > 600:
        desc += "…"
    lines.append(_esc(desc))
    return "\n".join(lines)


def build_post_text(opp: Opportunity, lang: str = "en") -> str:
    emoji = TYPE_EMOJI.get(opp.opportunity_type, "✨")
    header = f"{emoji} <b>{opp.opportunity_type.upper()}</b>"
    body = opp.edited_text if opp.edited_text else default_body(opp)

    facts = []
    facts.append(f"{t('detail_funding', lang)}: {t('funding_' + opp.funding_tier, lang)}")
    deadline = opp.deadline.isoformat() if opp.deadline else t("no_deadline", lang)
    facts.append(f"{t('detail_deadline', lang)}: {deadline}")
    if opp.country:
        facts.append(f"{t('detail_country', lang)}: {_esc(opp.country)}")
    if opp.fields:
        facts.append(f"{t('detail_fields', lang)}: {_esc(', '.join(opp.fields))}")
    facts.append(f"{t('detail_chance', lang)}: ~{opp.chance_percent}%")
    facts.append(t("eligibility_" + opp.armenian_eligibility, lang)
                 if opp.armenian_eligibility in ("ELIGIBLE", "UNCERTAIN") else "")
    if opp.english_req_score is not None:
        facts.append(t("english_req", lang,
                       req=f"{opp.english_req_test} {opp.english_req_score:g}"))

    footer = f"#opp{opp.id} #{opp.opportunity_type}"
    return "\n\n".join([header, body, "\n".join(f for f in facts if f), footer])


def build_post_keyboard(opp: Opportunity, bot_username: str, lang: str = "en") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=t("btn_apply", lang), url=opp.apply_url or opp.url)]]
    rows.append([
        InlineKeyboardButton(
            text=t("btn_details", lang),
            url=f"https://t.me/{bot_username}?start=opp_{opp.id}",
        ),
        InlineKeyboardButton(
            text=t("btn_analyze", lang),
            url=f"https://t.me/{bot_username}?start=fit_{opp.id}",
        ),
    ])
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
