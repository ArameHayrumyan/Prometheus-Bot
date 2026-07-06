"""APScheduler jobs: scraping cadences, reputation updates, expiry."""
from datetime import date
from urllib.parse import urlparse

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select, update

from app.config import get_settings
from app.constants import OppStatus
from app.db.base import session_scope
from app.db.models import AdminAction, Opportunity, Source, SourceReputation
from app.db.settings_service import get_setting, set_setting
from app.logging_setup import get_logger
from app.scraping.registry import active_sources, fetch_source
from app.pipeline.ingest import process_raw

log = get_logger("scheduler")


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
                for raw in raws:
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


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    s = get_settings()
    scheduler = AsyncIOScheduler(timezone=s.tz)
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
                      args=[bot, ["community"]], id="community", max_instances=1,
                      coalesce=True, misfire_grace_time=3600)
    scheduler.add_job(run_source_types, "interval", hours=s.linkedin_scrape_hours,
                      args=[bot, ["linkedin"]], id="linkedin", max_instances=1,
                      coalesce=True, misfire_grace_time=3600)
    scheduler.add_job(update_reputation, "cron", hour=3, minute=30, id="reputation")
    scheduler.add_job(expire_opportunities, "cron", hour=0, minute=15, id="expire")
    return scheduler
