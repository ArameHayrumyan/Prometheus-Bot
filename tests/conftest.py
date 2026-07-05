import os

# Minimal env so app.config can be imported by modules that need it in tests.
os.environ.setdefault("BOT_TOKEN", "0:test")
os.environ.setdefault("CHANNEL_ID_UNDERGRAD", "-100")
os.environ.setdefault("CHANNEL_ID_MASTERS", "-101")
os.environ.setdefault("CHANNEL_ID_PHD", "-102")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")

import pytest

from app.db import settings_service


@pytest.fixture(autouse=True)
def clear_settings_cache():
    settings_service.invalidate_cache()
    yield
    settings_service.invalidate_cache()


class FakeSettingsSession:
    """Stands in for AsyncSession where only settings lookups happen:
    session.get(AppSetting, key) -> None makes get_setting fall back to DEFAULTS."""

    async def get(self, model, key):
        return None


@pytest.fixture
def fake_settings_session():
    return FakeSettingsSession()
