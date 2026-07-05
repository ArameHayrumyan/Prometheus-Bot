"""Local sentence-transformers embeddings (CPU) + pgvector similarity lookup.

The model is loaded lazily in a thread so startup stays fast and the event
loop is never blocked by encode() calls.
"""
import asyncio
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Opportunity, OpportunityEmbedding
from app.logging_setup import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

log = get_logger("embeddings")

_model: "SentenceTransformer | None" = None
_model_lock = asyncio.Lock()


def _load_model() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model, device="cpu")


async def get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        async with _model_lock:
            if _model is None:
                log.info("loading_embedding_model", model=get_settings().embedding_model)
                _model = await asyncio.to_thread(_load_model)
    return _model


async def embed_text(text: str) -> list[float]:
    model = await get_model()
    vec = await asyncio.to_thread(model.encode, text[:4000], normalize_embeddings=True)
    return vec.tolist()


async def store_embedding(session: AsyncSession, opportunity_id: int, text: str) -> None:
    vec = await embed_text(text)
    existing = await session.get(OpportunityEmbedding, opportunity_id)
    if existing is None:
        session.add(OpportunityEmbedding(opportunity_id=opportunity_id, embedding=vec))
    else:
        existing.embedding = vec


async def similar_reviewed(session: AsyncSession, text: str, limit: int = 5) -> list[tuple[Opportunity, float]]:
    """The single RAG retrieval: nearest previously admin-reviewed opportunities."""
    vec = await embed_text(text)
    dist = OpportunityEmbedding.embedding.cosine_distance(vec)
    stmt = (
        select(Opportunity, dist.label("distance"))
        .join(OpportunityEmbedding, OpportunityEmbedding.opportunity_id == Opportunity.id)
        .where(Opportunity.status.in_(["APPROVED", "PUBLISHED", "REJECTED"]))
        .order_by(dist)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [(row[0], float(row[1])) for row in rows]
