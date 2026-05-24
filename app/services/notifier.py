import asyncio

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

log = structlog.get_logger(__name__)


class Notifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send(
        self,
        chat_id: int,
        text: str,
        session: AsyncSession | None = None,
    ) -> bool:
        try:
            await self._bot.send_message(chat_id, text, parse_mode="HTML")
            return True
        except TelegramRetryAfter as exc:
            log.warning("telegram_retry_after", chat_id=chat_id, retry_after=exc.retry_after)
            await asyncio.sleep(exc.retry_after)
            return await self.send(chat_id, text, session)
        except TelegramForbiddenError:
            log.info("user_blocked_bot", chat_id=chat_id)
            if session:
                from app.db.models import User
                result = await session.execute(
                    select(User).where(User.telegram_id == chat_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    user.is_blocked = True
                    await session.commit()
            return False
        except Exception as exc:
            log.error("send_message_failed", chat_id=chat_id, error=str(exc))
            return False

    async def notify_admin(self, text: str) -> None:
        await self.send(settings.admin_id, text)

    async def notify_user(
        self,
        user_id: int,
        text: str,
        session: AsyncSession | None = None,
    ) -> None:
        await self.send(user_id, text, session)
        await asyncio.sleep(0.05)
