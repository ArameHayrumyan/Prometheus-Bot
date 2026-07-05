"""AI tiebreaker for borderline legitimacy scores, grounded with a single
pgvector similarity lookup over previously admin-reviewed posts (few-shot).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import TIEBREAK_EXAMPLE, TIEBREAK_SYSTEM, TIEBREAK_TEMPLATE
from app.ai.router import get_router
from app.constants import OppStatus
from app.embeddings.service import similar_reviewed
from app.logging_setup import get_logger
from app.pipeline.normalize import Extracted

log = get_logger("pipeline.rag")


async def ai_tiebreak(session: AsyncSession, title: str, org: str | None,
                      description: str, extracted: Extracted) -> dict:
    """Returns {"verdict": "approve"|"reject", "confidence": int, "reason": str}.
    On total AI failure, fail open (approve) so a human still reviews the item —
    the admin queue is the real gate."""
    neighbors = await similar_reviewed(session, f"{title}\n{description[:1500]}", limit=5)
    examples = "\n".join(
        TIEBREAK_EXAMPLE.format(
            verdict="APPROVED" if opp.status in (OppStatus.APPROVED, OppStatus.PUBLISHED) else "REJECTED",
            title=opp.title[:120],
            opportunity_type=opp.opportunity_type,
            funding_tier=opp.funding_tier,
            snippet=opp.description[:150],
        )
        for opp, _dist in neighbors
    ) or "(no reviewed history yet)"

    prompt = TIEBREAK_TEMPLATE.format(
        title=title[:300],
        org=org or "unknown",
        opportunity_type=extracted.opportunity_type,
        funding_tier=extracted.funding_tier,
        duration=extracted.duration_days or "unknown",
        description=description[:2000],
        examples=examples,
    )
    try:
        result = await get_router().generate_json(session, TIEBREAK_SYSTEM, prompt, max_tokens=300)
        verdict = str(result.get("verdict", "approve")).lower()
        return {
            "verdict": verdict if verdict in ("approve", "reject") else "approve",
            "confidence": int(result.get("confidence", 50)),
            "reason": str(result.get("reason", ""))[:500],
        }
    except Exception as e:
        log.warning("tiebreak_failed_open", error=str(e)[:200])
        return {"verdict": "approve", "confidence": 0,
                "reason": f"AI unavailable ({str(e)[:100]}); passed to admin queue"}
