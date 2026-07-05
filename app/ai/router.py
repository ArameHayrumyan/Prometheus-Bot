"""Failover router across AI providers with live-configurable priority.

Priority order and the disabled-set live in app_settings (keys "ai_priority",
"ai_disabled") so admin commands change routing without a redeploy.
"""
import asyncio
import json
import random
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIError, AIProvider, AIRateLimited
from app.ai.providers import DeepSeekProvider, GeminiProvider, GroqProvider
from app.config import get_settings
from app.db.settings_service import get_setting
from app.logging_setup import get_logger

log = get_logger("ai.router")


class AllProvidersFailed(AIError):
    pass


class AIRouter:
    def __init__(self, providers: dict[str, AIProvider] | None = None):
        if providers is None:
            s = get_settings()
            providers = {
                "groq": GroqProvider(s.groq_api_key, s.groq_rpm),
                "deepseek": DeepSeekProvider(s.deepseek_api_key, s.deepseek_rpm),
                "gemini": GeminiProvider(s.gemini_api_key, s.gemini_rpm),
            }
        self.providers = providers

    async def _ordering(self, session: AsyncSession) -> list[AIProvider]:
        priority: list[str] = await get_setting(session, "ai_priority")
        disabled: list[str] = await get_setting(session, "ai_disabled")
        ordered = [
            self.providers[name]
            for name in priority
            if name in self.providers and name not in disabled
        ]
        # append any configured providers missing from the stored priority list
        for name, p in self.providers.items():
            if p not in ordered and name not in disabled:
                ordered.append(p)
        return [p for p in ordered if p.configured]

    async def generate(self, session: AsyncSession, system: str, user: str,
                       max_tokens: int = 1024, json_mode: bool = False,
                       attempts_per_provider: int = 2) -> str:
        ordered = await self._ordering(session)
        if not ordered:
            raise AllProvidersFailed("No AI provider is configured/enabled")
        last_err: Exception | None = None
        for provider in ordered:
            backoff = 1.5
            for attempt in range(attempts_per_provider):
                try:
                    return await provider.generate(system, user, max_tokens, json_mode)
                except AIRateLimited as e:
                    # don't hammer a rate-limited provider: fail over immediately
                    log.warning("ai_rate_limited", provider=provider.name, error=str(e)[:200])
                    last_err = e
                    break
                except AIError as e:
                    last_err = e
                    log.warning("ai_error", provider=provider.name,
                                attempt=attempt + 1, error=str(e)[:200])
                    if attempt + 1 < attempts_per_provider:
                        await asyncio.sleep(backoff + random.uniform(0, 0.5))
                        backoff *= 2
        raise AllProvidersFailed(f"All providers failed; last error: {last_err}")

    async def generate_json(self, session: AsyncSession, system: str, user: str,
                            max_tokens: int = 1024) -> dict:
        raw = await self.generate(session, system, user, max_tokens, json_mode=True)
        return parse_json_block(raw)

    def status(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "configured": p.configured,
                "requests": p.stats.requests,
                "errors": p.stats.errors,
                "rate_limits": p.stats.rate_limits,
                "errors_last_hour": p.stats.errors_last_hour,
                "last_error": p.stats.last_error,
            }
            for p in self.providers.values()
        ]


def parse_json_block(raw: str) -> dict:
    """Extract the first JSON object from a model response, tolerating fences."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise AIError(f"No JSON object in AI response: {raw[:200]}")
    return json.loads(m.group(0))


_router: AIRouter | None = None


def get_router() -> AIRouter:
    global _router
    if _router is None:
        _router = AIRouter()
    return _router
