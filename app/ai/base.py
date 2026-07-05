"""Common AI-provider interface. Each provider hides its own wire format."""
import abc
import asyncio
import time
from dataclasses import dataclass, field


class AIError(Exception):
    """Provider failed (network, 5xx, malformed response)."""


class AIRateLimited(AIError):
    """Provider returned 429 / quota exhausted."""


@dataclass
class ProviderStats:
    requests: int = 0
    errors: int = 0
    rate_limits: int = 0
    last_error: str | None = None
    recent_errors: list[float] = field(default_factory=list)  # monotonic timestamps

    def record_error(self, msg: str, rate_limited: bool = False) -> None:
        self.errors += 1
        if rate_limited:
            self.rate_limits += 1
        self.last_error = msg[:300]
        now = time.monotonic()
        self.recent_errors = [t for t in self.recent_errors if now - t < 3600] + [now]

    @property
    def errors_last_hour(self) -> int:
        now = time.monotonic()
        return len([t for t in self.recent_errors if now - t < 3600])


class RateLimiter:
    """Simple async requests-per-minute throttle (spacing-based token bucket)."""

    def __init__(self, rpm: int):
        self.min_interval = 60.0 / max(rpm, 1)
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._last + self.min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


class AIProvider(abc.ABC):
    name: str = "base"

    def __init__(self, api_key: str, rpm: int):
        self.api_key = api_key
        self.limiter = RateLimiter(rpm)
        self.stats = ProviderStats()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @abc.abstractmethod
    async def _generate(self, system: str, user: str, max_tokens: int, json_mode: bool) -> str:
        """Provider-specific request. Raise AIRateLimited / AIError on failure."""

    async def generate(self, system: str, user: str, max_tokens: int = 1024,
                       json_mode: bool = False) -> str:
        await self.limiter.acquire()
        self.stats.requests += 1
        try:
            return await self._generate(system, user, max_tokens, json_mode)
        except AIRateLimited as e:
            self.stats.record_error(str(e), rate_limited=True)
            raise
        except AIError as e:
            self.stats.record_error(str(e))
            raise
        except Exception as e:  # network errors etc. -> normalize
            self.stats.record_error(repr(e))
            raise AIError(f"{self.name}: {e!r}") from e
