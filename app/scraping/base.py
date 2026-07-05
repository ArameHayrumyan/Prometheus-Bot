"""Shared handler interface + the raw payload every acquisition channel emits."""
import abc
from dataclasses import dataclass, field
from datetime import datetime

from app.db.models import Source


@dataclass
class RawOpportunity:
    source_id: int
    url: str
    title: str
    text: str
    org: str | None = None
    posted_at: datetime | None = None
    extra: dict = field(default_factory=dict)


class SourceHandler(abc.ABC):
    """One handler class per acquisition mechanism (source_type)."""

    source_type: str = ""

    @abc.abstractmethod
    async def fetch(self, source: Source) -> list[RawOpportunity]:
        """Fetch current listings for one registered source.

        Must swallow per-item errors and raise only on total failure;
        the scheduler logs and continues either way.
        """
