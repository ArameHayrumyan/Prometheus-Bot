"""APScheduler jobs: scraping cadences, reputation updates, expiry,
deadline reminders, application-outcome follow-ups, weekly channel digests."""
import html
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select, update

from app.config import get_settings
from app.constants import OppStatus
from app.db.base import session_scope
from app.db.models import (AdminAction, Channel, Opportunity, SavedOpportunity,
                           Source, SourceReputation, User)
from app.db.settings_service import get_setting, set_setting
from app.i18n import t
from app.logging_setup import get_logger
from app.scraping.registry import active_sources, fetch_source
from app.pipeline.ingest import process_raw

log = get_logger("scheduler")

REMINDER_DAYS = (7, 3, 1)


def reminder_day_due(deadline: date, sent_days: list, today: date) -> int | None:
    """Which reminder (7/3/1 days-before) is due today, if any. Pure/testable."""
    days_left = (deadline - today).days
    if days_left in REMINDER_DAYS and days_left not in sent_days:
        return days_left
    return None


async def run_source_types(bot: Bot, source_types: list[str],
                           notify_admins: bool = True) -> int:
    """Fetch every active source of the given types; each source gets its own
    transaction so one failure never poisons the batch. Returns the number of
    new items queued for review."""
    settings = get_settings()
    new_pending = 0
    async with session_scope() as session:
        sources = await active_sources(session, source_types)
        source_ids = [s.id for s in sources]
    for source_id in source_ids:
        try:
            async with session_scope() as session:
                source = await session.get(Source, source_id)
                if source is None or not source.active:
                    continue
                raws = await fetch_source(session, source)
                audience = (source.meta or {}).get("audience", "student")
                # cap per source so mega-boards can't drown niche sources;
                # per-source override via meta.max_items
                cap = int((source.meta or {}).get(
                    "max_items", await get_setting(session, "max_items_per_source")))
                for raw in raws[:cap]:
                    raw.audience = audience
                    opp = await process_raw(session, raw)
                    if opp is not None:
                        new_pending += 1
        except Exception as e:
            log.error("source_job_failed", source_id=source_id, error=str(e)[:300])
    if new_pending and notify_admins:
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    f"📥 {new_pending} new opportunit{'y' if new_pending == 1 else 'ies'} "
                    f"awaiting review — /queue",
                )
            except Exception as e:
                log.info("admin_notify_failed", admin=admin_id, error=str(e)[:150])
    log.info("scrape_cycle_done", types=source_types, new_pending=new_pending)
    return new_pending


async def update_reputation() -> None:
    """Moving-average reputation per domain from admin approve/reject history,
    plus a bounded heuristic adjustment of the AI-tiebreak band (§9)."""
    async with session_scope() as session:
        rows = (await session.execute(
            select(Opportunity.url, AdminAction.action, func.count())
            .join(AdminAction, AdminAction.opportunity_id == Opportunity.id)
            .where(AdminAction.action.in_(["approve", "reject"]))
            .group_by(Opportunity.url, AdminAction.action)
        )).all()
        per_domain: dict[str, dict[str, int]] = {}
        for url, action, count in rows:
            domain = urlparse(url).netloc.lower().removeprefix("www.")
            per_domain.setdefault(domain, {"approve": 0, "reject": 0})[action] += count

        for domain, counts in per_domain.items():
            total = counts["approve"] + counts["reject"]
            if total == 0:
                continue
            batch_ratio = counts["approve"] / total
            rep = (await session.execute(
                select(SourceReputation).where(SourceReputation.domain == domain)
            )).scalar_one_or_none()
            if rep is None:
                rep = SourceReputation(domain=domain, score=0.5)
                session.add(rep)
            rep.score = round(0.7 * rep.score + 0.3 * batch_ratio, 3)
            rep.approved_count = counts["approve"]
            rep.rejected_count = counts["reject"]

        # band adjustment: if borderline items are overwhelmingly approved,
        # relax the lower bound a little; if overwhelmingly rejected, tighten.
        band = list(await get_setting(session, "borderline_band"))
        stats = (await session.execute(
            select(AdminAction.action, func.count())
            .join(Opportunity, Opportunity.id == AdminAction.opportunity_id)
            .where(AdminAction.action.in_(["approve", "reject"]),
                   Opportunity.legitimacy_score.between(band[0], band[0] + 10))
            .group_by(AdminAction.action)
        )).all()
        counts = dict(stats)
        total = counts.get("approve", 0) + counts.get("reject", 0)
        if total >= 10:
            ratio = counts.get("approve", 0) / total
            if ratio > 0.7 and band[0] > 20:
                band[0] -= 1
            elif ratio < 0.2 and band[0] < band[1] - 5:
                band[0] += 1
            await set_setting(session, "borderline_band", band)
    log.info("reputation_updated", domains=len(per_domain))


async def expire_opportunities() -> None:
    async with session_scope() as session:
        result = await session.execute(
            update(Opportunity)
            .where(Opportunity.deadline.is_not(None),
                   Opportunity.deadline < date.today(),
                   Opportunity.status.in_([OppStatus.PENDING_REVIEW, OppStatus.ARCHIVED,
                                           OppStatus.PUBLISHED, OppStatus.APPROVED]))
            .values(status=OppStatus.EXPIRED)
        )
        log.info("expired_marked", count=result.rowcount)


async def send_deadline_reminders(bot: Bot) -> None:
    """Daily 10:00 Yerevan: DM users about saved items 7/3/1 days from deadline.
    Skips muted saves and items the user already applied to."""
    from app.bot.keyboards import kb

    today = date.today()
    sent = 0
    async with session_scope() as session:
        rows = (await session.execute(
            select(SavedOpportunity, Opportunity, User)
            .join(Opportunity, Opportunity.id == SavedOpportunity.opportunity_id)
            .join(User, User.tg_id == SavedOpportunity.user_tg_id)
            .where(SavedOpportunity.remind.is_(True),
                   SavedOpportunity.applied_at.is_(None),
                   Opportunity.deadline.is_not(None),
                   Opportunity.deadline >= today,
                   Opportunity.deadline <= today + timedelta(days=max(REMINDER_DAYS)))
        )).all()
        for saved, opp, user in rows:
            due = reminder_day_due(opp.deadline, saved.reminders_sent or [], today)
            if due is None:
                continue
            lang = user.language
            text = t("reminder_msg", lang, days=due,
                     title=html.escape(opp.title[:120], quote=False),
                     deadline=opp.deadline.isoformat())
            try:
                await bot.send_message(
                    user.tg_id, text, parse_mode="HTML",
                    reply_markup=kb([
                        [(t("btn_details", lang), f"svd:{saved.id}"),
                         (t("btn_applied", lang), f"svapp:{saved.id}")],
                        [("🔕", f"svmute:{saved.id}")],
                    ]),
                )
                saved.reminders_sent = list(saved.reminders_sent or []) + [due]
                sent += 1
            except Exception as e:
                log.info("reminder_failed", user=user.tg_id, error=str(e)[:150])
    log.info("reminders_sent", count=sent)


async def ask_outcomes(bot: Bot) -> None:
    """Daily: ~30 days after a deadline, ask users who applied how it went.
    'Still waiting' answers get re-asked after another 30 days."""
    from app.bot.keyboards import kb

    now = datetime.now(timezone.utc)
    cutoff_deadline = date.today() - timedelta(days=30)
    re_ask_before = now - timedelta(days=30)
    asked = 0
    async with session_scope() as session:
        rows = (await session.execute(
            select(SavedOpportunity, Opportunity, User)
            .join(Opportunity, Opportunity.id == SavedOpportunity.opportunity_id)
            .join(User, User.tg_id == SavedOpportunity.user_tg_id)
            .where(SavedOpportunity.applied_at.is_not(None),
                   SavedOpportunity.outcome.is_(None),
                   Opportunity.deadline.is_not(None),
                   Opportunity.deadline <= cutoff_deadline)
        )).all()
        for saved, opp, user in rows:
            if saved.outcome_asked_at is not None and saved.outcome_asked_at > re_ask_before:
                continue
            lang = user.language
            try:
                await bot.send_message(
                    user.tg_id,
                    t("outcome_q", lang, title=html.escape(opp.title[:120], quote=False)),
                    parse_mode="HTML",
                    reply_markup=kb([
                        [(t("outcome_accepted_btn", lang), f"svout:{saved.id}:accepted"),
                         (t("outcome_rejected_btn", lang), f"svout:{saved.id}:rejected")],
                        [(t("outcome_waiting_btn", lang), f"svout:{saved.id}:waiting")],
                    ]),
                )
                saved.outcome_asked_at = now
                asked += 1
            except Exception as e:
                log.info("outcome_ask_failed", user=user.tg_id, error=str(e)[:150])
    log.info("outcomes_asked", count=asked)


def pick_digest_items(opps: list, limit: int = 5, minimum: int = 3) -> list:
    """Top open items for a weekly digest: soonest deadline first, chance as
    tiebreaker; empty list when below the minimum. Pure/testable."""
    ranked = sorted(opps, key=lambda o: (o.deadline, -o.chance_percent))
    if len(ranked) < minimum:
        return []
    return ranked[:limit]


async def build_digest_text(session, bot_username: str, today: date) -> str | None:
    """Compile the unified channel's closing-soon digest (all audiences,
    youth items marked 🌱), or None when under the minimum."""
    opps = (await session.execute(
        select(Opportunity)
        .where(Opportunity.status == OppStatus.PUBLISHED,
               Opportunity.deadline.is_not(None),
               Opportunity.deadline >= today,
               Opportunity.deadline <= today + timedelta(days=60))
    )).scalars().all()
    picked = pick_digest_items(list(opps))
    if not picked:
        return None
    lines = [t("digest_header"), ""]
    for i, opp in enumerate(picked, 1):
        days_left = (opp.deadline - today).days
        link = f"https://t.me/{bot_username}?start=opp_{opp.id}"
        mark = "🌱 " if opp.audience == "youth" else ""
        lines.append(
            f"{i}. {mark}<a href=\"{link}\">{html.escape(opp.title[:80], quote=False)}</a>\n"
            f"   📅 {opp.deadline} ({days_left}d left) · 🎯 ~{opp.chance_percent}%"
        )
    lines.append("")
    lines.append(t("digest_footer"))
    return "\n".join(lines)[:4096]


async def weekly_digest(bot: Bot) -> None:
    """Sunday 19:00 Yerevan: compile the main-channel digest and send it to
    the ADMINS for approval — nothing is ever posted automatically."""
    from app.bot.keyboards import kb

    me = await bot.get_me()
    today = date.today()
    settings = get_settings()
    async with session_scope() as session:
        main = (await session.execute(
            select(Channel).where(Channel.audience == "main")
        )).scalars().first()
        if main is None:
            log.warning("digest_no_main_channel")
            return
        text = await build_digest_text(session, me.username or "", today)
        if text is None:
            log.info("digest_skipped_below_minimum")
            return
        preview = f"🗓 Weekly digest preview — post it?\n{'─' * 20}\n\n{text}"
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(
                    admin_id, preview[:4096], parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=kb([[("📣 Post to channel", f"dg:post:{main.id}"),
                                      ("✖️ Skip this week", f"dg:skip:{main.id}")]]),
                )
            except Exception as e:
                log.info("digest_preview_failed", admin=admin_id, error=str(e)[:150])


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    s = get_settings()
    scheduler = AsyncIOScheduler(timezone=s.tz)
    if s.run_scraper_jobs:
        scheduler.add_job(run_source_types, "interval", minutes=s.rss_poll_minutes,
                          args=[bot, ["rss"]], id="rss", max_instances=1, coalesce=True,
                          misfire_grace_time=300)
        scheduler.add_job(run_source_types, "interval", minutes=s.newsletter_poll_minutes,
                          args=[bot, ["email"]], id="email", max_instances=1, coalesce=True,
                          misfire_grace_time=300)
        scheduler.add_job(run_source_types, "interval", hours=s.web_scrape_hours,
                          args=[bot, ["webpage"]], id="webpage", max_instances=1, coalesce=True,
                          misfire_grace_time=3600)
        scheduler.add_job(run_source_types, "interval", hours=s.community_scrape_hours,
                          args=[bot, ["community", "telegram"]], id="community",
                          max_instances=1, coalesce=True, misfire_grace_time=3600)
        scheduler.add_job(run_source_types, "interval", hours=s.linkedin_scrape_hours,
                          args=[bot, ["linkedin"]], id="linkedin", max_instances=1,
                          coalesce=True, misfire_grace_time=3600)
    else:
        log.info("scraper_jobs_disabled", hint="run scraping via app.scraper_cli")
    scheduler.add_job(update_reputation, "cron", hour=3, minute=30, id="reputation")
    scheduler.add_job(expire_opportunities, "cron", hour=0, minute=15, id="expire")
    scheduler.add_job(send_deadline_reminders, "cron", hour=10, minute=0,
                      args=[bot], id="reminders", misfire_grace_time=3600)
    scheduler.add_job(ask_outcomes, "cron", hour=10, minute=10,
                      args=[bot], id="outcomes", misfire_grace_time=3600)
    scheduler.add_job(weekly_digest, "cron", day_of_week="sun", hour=19, minute=0,
                      args=[bot], id="digest", misfire_grace_time=3600)
    return scheduler
