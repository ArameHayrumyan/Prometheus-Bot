"""Read/write live-tunable settings stored in app_settings, with a small TTL cache."""
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSetting

DEFAULTS: dict[str, Any] = {
    "scoring_weights": {"acceptance": 0.5, "selectivity": 0.2, "requirements": 0.3},
    "borderline_band": [40, 65],
    "min_duration_days": 15,
    "ai_priority": ["groq", "deepseek", "gemini"],
    "enrich_daily_cap": 50,
    # cap items ingested per source per cycle so mega-boards (RemoteOK,
    # WeWorkRemotely: 50 each) can't drown niche/low-competition sources
    "max_items_per_source": 12,
    "ai_disabled": [],
    "noise_keywords": [
        "leadership camp", "youth summit", "youth forum", "networking event",
        "cultural exchange", "model united nations", "mun conference",
        "youth exchange", "study tour", "leadership summit", "youth leadership",
        "young leaders forum", "delegate program",
    ],
    "deliverable_keywords": [
        "certificate", "certification", "stipend", "salary", "publication",
        "research project", "curriculum", "thesis", "capstone", "portfolio",
        "diploma", "credential", "paid position", "prize", "mentorship program",
        "work experience", "job offer", "full-time offer",
    ],
    "prestige_domains": [
        "google.com", "deepmind.com", "microsoft.com", "apple.com", "meta.com",
        "openai.com", "embl.org", "broadinstitute.org", "sanger.ac.uk",
        "mpg.de", "ethz.ch", "epfl.ch", "mit.edu", "stanford.edu", "ox.ac.uk",
        "cam.ac.uk", "nasa.gov", "cern.ch",
    ],
}

_cache: dict[str, tuple[float, Any]] = {}
_TTL = 60.0


async def get_setting(session: AsyncSession, key: str) -> Any:
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    row = await session.get(AppSetting, key)
    value = row.value if row is not None else DEFAULTS.get(key)
    _cache[key] = (now, value)
    return value


async def set_setting(session: AsyncSession, key: str, value: Any) -> None:
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    _cache[key] = (time.monotonic(), value)


async def all_settings(session: AsyncSession) -> dict[str, Any]:
    rows = (await session.execute(select(AppSetting))).scalars().all()
    merged = dict(DEFAULTS)
    merged.update({r.key: r.value for r in rows})
    return merged


def invalidate_cache() -> None:
    _cache.clear()
