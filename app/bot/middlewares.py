"""DB session + user-loading middleware for every update."""
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.db.base import get_session_factory
from app.db.models import User


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        factory = get_session_factory()
        async with factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class UserMiddleware(BaseMiddleware):
    """Loads (or creates) the User row and exposes `user` + `lang`."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        session = data.get("session")
        if tg_user is not None and session is not None:
            user = await session.get(User, tg_user.id)
            if user is None:
                lang = "hy" if (tg_user.language_code or "").startswith("hy") else "en"
                user = User(tg_id=tg_user.id, language=lang)
                session.add(user)
                await session.flush()
            data["user"] = user
            data["lang"] = user.language
        return await handler(event, data)
