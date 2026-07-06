"""Approve-time AI post enrichment (TL;DR, competitiveness, requirement bullets).

Token frugality, by design:
- runs only when an admin taps Approve (never at ingest);
- one JSON call per opportunity, small max_tokens, cached on the row forever;
- hard daily cap (app_settings "enrich_daily_cap", default 50, /setcap) —
  when the cap is hit or the AI fails, publishing proceeds with the
  regex-extracted content exactly as before.
"""
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import ENRICH_SYSTEM, ENRICH_TEMPLATE
from app.ai.router import get_router
from app.db.models import Opportunity
from app.db.settings_service import get_setting, set_setting
from app.logging_setup import get_logger

log = get_logger("ai.enrich")


def normalize_enrichment(raw: dict) -> dict | None:
    """Validate/trim a model response; None means unusable (fall back to regex)."""
    tldr = str(raw.get("tldr", "")).strip()
    if len(tldr) < 20:
        return None
    bullets = [str(b).strip()[:150] for b in raw.get("requirements", []) if str(b).strip()]
    return {
        "tldr": tldr[:800],
        "competitiveness": str(raw.get("competitiveness", "")).strip()[:300],
        "requirements": bullets[:5],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _cap_allows(session: AsyncSession) -> bool:
    """Check-and-increment the daily counter (persisted in app_settings)."""
    cap = int(await get_setting(session, "enrich_daily_cap"))
    used = await get_setting(session, "enrich_used") or {}
    today = date.today().isoformat()
    count = used.get("count", 0) if used.get("date") == today else 0
    if count >= cap:
        log.info("enrich_cap_reached", cap=cap)
        return False
    await set_setting(session, "enrich_used", {"date": today, "count": count + 1})
    return True


async def enrich_opportunity(session: AsyncSession, opp: Opportunity) -> dict | None:
    """Returns the enrichment dict, or None (cap hit / AI failed / thin output).
    Idempotent: an already-enriched row never spends tokens again."""
    if opp.enrichment:
        return opp.enrichment
    if not await _cap_allows(session):
        return None
    prompt = ENRICH_TEMPLATE.format(
        title=opp.title[:300],
        org=opp.org or "unknown",
        opportunity_type=opp.opportunity_type,
        funding_tier=opp.funding_tier,
        deadline=opp.deadline or "not stated",
        duration=opp.duration_days or "not stated",
        spots=opp.spots or "not stated",
        acceptance_rate=f"{opp.acceptance_rate}%" if opp.acceptance_rate else "not stated",
        chance=opp.chance_percent,
        description=opp.description[:2500],
    )
    try:
        raw = await get_router().generate_json(session, ENRICH_SYSTEM, prompt, max_tokens=450)
    except Exception as e:
        log.warning("enrich_failed", opp_id=opp.id, error=str(e)[:200])
        return None
    enrichment = normalize_enrichment(raw)
    if enrichment is None:
        log.info("enrich_output_unusable", opp_id=opp.id)
        return None
    opp.enrichment = enrichment
    await session.flush()
    return enrichment
