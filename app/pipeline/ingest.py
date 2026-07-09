"""Ingest orchestration: raw item -> dedupe -> extract -> hard gate -> scoring
-> optional AI tiebreak -> PENDING_REVIEW (admin queue) or DISCARDED (log).
"""
import re
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import Eligibility, OppStatus
from app.db.models import FieldTaxonomy, Opportunity, Source, SourceReputation
from app.db.settings_service import get_setting
from app.embeddings.service import store_embedding
from app.logging_setup import get_logger
from app.pipeline import hard_gate, normalize, scoring
from app.pipeline.rag import ai_tiebreak
from app.scraping.base import RawOpportunity

log = get_logger("pipeline.ingest")


async def load_taxonomy(session: AsyncSession) -> dict[str, list[str]]:
    rows = (await session.execute(
        select(FieldTaxonomy).where(FieldTaxonomy.active.is_(True))
    )).scalars().all()
    return {r.name: [kw.lower() for kw in r.keywords] for r in rows}


async def get_reputation(session: AsyncSession, url: str) -> float:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    row = (await session.execute(
        select(SourceReputation).where(SourceReputation.domain == domain)
    )).scalar_one_or_none()
    return row.score if row else 0.5


async def resolve_country(session: AsyncSession, raw: RawOpportunity,
                          extracted_country: str | None) -> str | None:
    """Give the opportunity a country so the country filter is meaningful:
    text-extracted country > the source's known country > 'Remote' if the
    listing says so. Without this, opp.country is almost always empty."""
    if extracted_country:
        return extracted_country
    if raw.source_id is not None:
        src = await session.get(Source, raw.source_id)
        if src and src.country:
            return src.country
    if re.search(r"\bremote\b", f"{raw.title}\n{raw.text[:600]}", re.IGNORECASE):
        return "Remote"
    return None


async def already_seen(session: AsyncSession, raw_hash: str) -> bool:
    return (await session.execute(
        select(Opportunity.id).where(Opportunity.raw_hash == raw_hash)
    )).scalar_one_or_none() is not None


async def process_raw(session: AsyncSession, raw: RawOpportunity) -> Opportunity | None:
    """Run one raw item through the full pipeline. Returns the Opportunity row
    if it reached PENDING_REVIEW, else None (duplicate or discarded)."""
    raw_hash = normalize.content_hash(raw.url, raw.title)
    if await already_seen(session, raw_hash):
        return None

    taxonomy = await load_taxonomy(session)
    noise_keywords = await get_setting(session, "noise_keywords")
    deliverable_keywords = await get_setting(session, "deliverable_keywords")
    min_duration = int(await get_setting(session, "min_duration_days"))

    extracted = normalize.extract_all(
        raw.title, raw.text, taxonomy, noise_keywords, deliverable_keywords
    )
    gate = hard_gate.evaluate(extracted, min_duration, youth=(raw.audience == "youth"))

    # org: handler-provided, else extracted from title/first lines, else the
    # source domain as a readable last resort (never "unknown")
    org = (raw.org
           or normalize.extract_org(raw.title, raw.text)
           or urlparse(raw.url).netloc.lower().removeprefix("www."))

    opp = Opportunity(
        source_id=raw.source_id,
        url=raw.url,
        raw_hash=raw_hash,
        title=raw.title,
        org=org,
        description=raw.text[:8000],
        opportunity_type=extracted.opportunity_type,
        audience=raw.audience,
        degree_levels=extracted.degree_levels,
        fields=extracted.fields_matched,
        country=await resolve_country(session, raw, extracted.country),
        deadline=extracted.deadline,
        duration_days=extracted.duration_days,
        funding_tier=extracted.funding_tier,
        armenian_eligibility=(
            Eligibility.UNCERTAIN if gate.uncertain_eligibility else extracted.armenian_eligibility
        ),
        english_req_test=extracted.english_req_test,
        english_req_score=extracted.english_req_score,
        spots=extracted.spots,
        acceptance_rate=extracted.acceptance_rate,
        requirements=extracted.requirements,
        apply_url=raw.url,
    )

    if not gate.passed:
        # silent discard log — visible only via the admin /discards command
        opp.status = OppStatus.DISCARDED
        opp.discard_reason = gate.discard_reason
        session.add(opp)
        await session.flush()
        log.info("discarded", title=raw.title[:80], reason=gate.discard_reason)
        return None

    reputation = await get_reputation(session, raw.url)
    prestige_domains = await get_setting(session, "prestige_domains")
    domain = urlparse(raw.url).netloc.lower().removeprefix("www.")
    is_prestige = any(domain == d or domain.endswith("." + d) for d in prestige_domains)

    opp.legitimacy_score = scoring.legitimacy_score(
        extracted, reputation, is_prestige, youth=(raw.audience == "youth"))
    weights = await get_setting(session, "scoring_weights")
    opp.chance_percent = scoring.chance_percent(
        extracted, weights, reputation, is_prestige, student=None
    )

    band = await get_setting(session, "borderline_band")
    if opp.legitimacy_score < band[0]:
        opp.status = OppStatus.DISCARDED
        opp.discard_reason = f"legitimacy score {opp.legitimacy_score} below band {band}"
        session.add(opp)
        await session.flush()
        log.info("discarded_low_legitimacy", title=raw.title[:80], score=opp.legitimacy_score)
        return None

    if scoring.in_borderline_band(opp.legitimacy_score, band):
        verdict = await ai_tiebreak(session, raw.title, raw.org, raw.text, extracted)
        opp.ai_verdict = verdict
        if verdict["verdict"] == "reject" and verdict["confidence"] >= 60:
            opp.status = OppStatus.DISCARDED
            opp.discard_reason = f"AI tiebreak reject: {verdict['reason']}"
            session.add(opp)
            await session.flush()
            log.info("discarded_ai_tiebreak", title=raw.title[:80], reason=verdict["reason"])
            return None

    opp.status = OppStatus.PENDING_REVIEW
    session.add(opp)
    await session.flush()
    try:
        await store_embedding(session, opp.id, f"{opp.title}\n{opp.description[:1500]}")
    except Exception as e:
        log.warning("embedding_failed", opp_id=opp.id, error=str(e)[:200])
    log.info("queued_for_review", opp_id=opp.id, title=raw.title[:80],
             legitimacy=opp.legitimacy_score, chance=opp.chance_percent)
    return opp
