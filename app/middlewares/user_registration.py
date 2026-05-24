from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User

log = structlog.get_logger(__name__)


class UserRegistrationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession | None = data.get("session")
        from_user = data.get("event_from_user")

        if session is None or from_user is None or from_user.is_bot:
            return await handler(event, data)

        result = await session.execute(
            select(User).where(User.telegram_id == from_user.id)
        )
        user = result.scalar_one_or_none()
        is_new = False

        if user is None:
            user = User(
                telegram_id=from_user.id,
                username=from_user.username,
                first_name=from_user.first_name or "",
                language_code=from_user.language_code,
            )
            session.add(user)
            await session.commit()
            is_new = True
            log.info("new_user_registered", user_id=from_user.id, username=from_user.username)
        else:
            changed = (
                user.username != from_user.username
                or user.first_name != (from_user.first_name or "")
            )
            if changed:
                user.username = from_user.username
                user.first_name = from_user.first_name or ""
                await session.commit()
            if user.is_blocked:
                user.is_blocked = False
                await session.commit()

        data["db_user"] = user
        response = await handler(event, data)

        if is_new:
            bot = data.get("bot")
            if bot:
                name_part = (
                    f"@{from_user.username}"
                    if from_user.username
                    else from_user.first_name or str(from_user.id)
                )
                try:
                    await bot.send_message(
                        settings.admin_id,
                        f"🆕 <b>New user</b>\n"
                        f"{name_part} | <code>{from_user.id}</code>",
                        parse_mode="HTML",
                    )
                except Exception as exc:
                    log.warning("admin_notify_failed", error=str(exc))

        return response
