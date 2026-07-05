"""'Analyze my fit' (§11): student documents vs opportunity requirements."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import FIT_SYSTEM, FIT_TEMPLATE
from app.ai.router import get_router
from app.db.models import AnalysisResult, Document, Opportunity, User
from app.logging_setup import get_logger

log = get_logger("analysis.fit")


async def user_documents(session: AsyncSession, user_tg_id: int) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.user_tg_id == user_tg_id)
        .order_by(
            # resumes first, then covers/notes, newest first within a type
            Document.doc_type != "resume",
            Document.created_at.desc(),
        )
    )
    return list((await session.execute(stmt)).scalars().all())


async def has_resume(session: AsyncSession, user_tg_id: int) -> bool:
    stmt = select(Document.id).where(
        Document.user_tg_id == user_tg_id, Document.doc_type == "resume"
    ).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


def _docs_blob(docs: list[Document], limit: int = 9000) -> str:
    parts: list[str] = []
    used = 0
    for doc in docs:
        chunk = f"--- {doc.doc_type.upper()}: {doc.filename} ---\n{doc.extracted_text}"
        remaining = limit - used
        if remaining <= 0:
            break
        parts.append(chunk[:remaining])
        used += len(parts[-1])
    return "\n\n".join(parts)


async def analyze_fit(session: AsyncSession, user: User, opp: Opportunity) -> dict:
    """Returns {"match_score": int, "gaps": [...], "suggestions": [...],
    "resume_bullets": [...]} and persists an AnalysisResult row."""
    docs = await user_documents(session, user.tg_id)
    english = (
        f"{user.english_test} {user.english_score} (expires {user.english_expiry})"
        if user.english_test else "no certificate on file"
    )
    prompt = FIT_TEMPLATE.format(
        title=opp.title[:300],
        org=opp.org or "unknown",
        opportunity_type=opp.opportunity_type,
        degree_levels=", ".join(opp.degree_levels or []),
        requirements=opp.requirements or "(not explicitly stated — infer from description)",
        description=opp.description[:2500],
        degree_level=user.degree_level_code or "unknown",
        fields=", ".join(user.fields or []) or "unknown",
        gpa=user.gpa if user.gpa is not None else "not provided",
        english=english,
        documents=_docs_blob(docs),
    )
    result = await get_router().generate_json(session, FIT_SYSTEM, prompt, max_tokens=1200)
    normalized = {
        "match_score": int(result.get("match_score", 0)),
        "gaps": [str(g) for g in result.get("gaps", [])][:10],
        "suggestions": [str(s) for s in result.get("suggestions", [])][:10],
        "resume_bullets": [str(b) for b in result.get("resume_bullets", [])][:8],
    }
    session.add(AnalysisResult(
        user_tg_id=user.tg_id, opportunity_id=opp.id, result=normalized,
    ))
    await session.flush()
    return normalized
