"""AI router: failover order, rate-limit skip, disable/enable, priority changes."""
import pytest

from app.ai.base import AIError, AIProvider, AIRateLimited
from app.ai.router import AIRouter, AllProvidersFailed, parse_json_block
from app.db.settings_service import DEFAULTS, _cache
import time


class FakeProvider(AIProvider):
    def __init__(self, name: str, behavior: str = "ok", reply: str = "hello"):
        super().__init__(api_key="test-key", rpm=10000)
        self.name = name
        self.behavior = behavior
        self.reply = reply
        self.calls = 0

    async def _generate(self, system, user, max_tokens, json_mode):
        self.calls += 1
        if self.behavior == "rate_limit":
            raise AIRateLimited(f"{self.name}: 429")
        if self.behavior == "error":
            raise AIError(f"{self.name}: boom")
        return self.reply


def make_router(**behaviors) -> tuple[AIRouter, dict[str, FakeProvider]]:
    providers = {
        name: FakeProvider(name, behaviors.get(name, "ok"), reply=f"from-{name}")
        for name in ("groq", "deepseek", "gemini")
    }
    return AIRouter(providers=providers), providers


def _prime(key, value):
    _cache[key] = (time.monotonic(), value)


async def test_uses_first_priority_provider(fake_settings_session):
    router, providers = make_router()
    result = await router.generate(fake_settings_session, "sys", "hi")
    assert result == "from-groq"  # default priority: groq first
    assert providers["deepseek"].calls == 0


async def test_rate_limited_provider_fails_over_immediately(fake_settings_session):
    router, providers = make_router(groq="rate_limit")
    result = await router.generate(fake_settings_session, "sys", "hi")
    assert result == "from-deepseek"
    assert providers["groq"].calls == 1  # no retry hammering on 429


async def test_error_provider_retries_then_fails_over(fake_settings_session):
    router, providers = make_router(groq="error")
    result = await router.generate(fake_settings_session, "sys", "hi",
                                   attempts_per_provider=2)
    assert result == "from-deepseek"
    assert providers["groq"].calls == 2  # retried with backoff before failover
    assert providers["groq"].stats.errors == 2


async def test_all_failing_raises(fake_settings_session):
    router, _ = make_router(groq="error", deepseek="rate_limit", gemini="error")
    with pytest.raises(AllProvidersFailed):
        await router.generate(fake_settings_session, "sys", "hi",
                              attempts_per_provider=1)


async def test_disabled_provider_is_skipped(fake_settings_session):
    _prime("ai_priority", DEFAULTS["ai_priority"])
    _prime("ai_disabled", ["groq"])
    router, providers = make_router()
    result = await router.generate(fake_settings_session, "sys", "hi")
    assert result == "from-deepseek"
    assert providers["groq"].calls == 0


async def test_priority_change_is_live(fake_settings_session):
    _prime("ai_priority", ["gemini", "groq", "deepseek"])
    _prime("ai_disabled", [])
    router, providers = make_router()
    result = await router.generate(fake_settings_session, "sys", "hi")
    assert result == "from-gemini"


def test_parse_json_block_tolerates_fences():
    assert parse_json_block('{"a": 1}') == {"a": 1}
    assert parse_json_block('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_block('Sure! Here you go:\n{"verdict": "reject"} thanks') == {
        "verdict": "reject"
    }
