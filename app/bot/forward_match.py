"""Forward-to-bot matching (§12): recognize which opportunity a forwarded
channel post refers to.

Primary: (channel_id, message_id) from forward_origin -> channel_posts table.
Fallback: the #opp<ID> tag embedded in every published post's text.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChannelPost, Opportunity

OPP_TAG_RE = re.compile(r"#opp(\d+)\b")


def extract_opp_id(text: str | None) -> int | None:
    if not text:
        return None
    m = OPP_TAG_RE.search(text)
    return int(m.group(1)) if m else None


async def resolve_forwarded(
    session: AsyncSession,
    origin_chat_id: int | None,
    origin_message_id: int | None,
    text: str | None,
) -> Opportunity | None:
    if origin_chat_id is not None and origin_message_id is not None:
        stmt = (
            select(Opportunity)
            .join(ChannelPost, ChannelPost.opportunity_id == Opportunity.id)
            .where(
                ChannelPost.tg_channel_id == origin_chat_id,
                ChannelPost.message_id == origin_message_id,
            )
        )
        opp = (await session.execute(stmt)).scalar_one_or_none()
        if opp is not None:
            return opp
    opp_id = extract_opp_id(text)
    if opp_id is not None:
        return await session.get(Opportunity, opp_id)
    return None
