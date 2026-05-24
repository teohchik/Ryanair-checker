from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Subscription, User
from app.filters.admin import IsAdmin
from app.services import price_tracker

router = Router()
router.message.filter(IsAdmin())


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    total_users = await session.scalar(select(func.count()).select_from(User))
    active_subs = await session.scalar(
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.is_active.is_(True))
    )
    last_run = price_tracker.get_last_run()
    last_run_text = (
        last_run.strftime("%Y-%m-%d %H:%M UTC") if last_run else "not run yet"
    )
    await message.answer(
        f"📊 <b>Bot stats</b>\n\n"
        f"👥 Users: <b>{total_users}</b>\n"
        f"🔔 Active trackers: <b>{active_subs}</b>\n"
        f"🕐 Last price check: <b>{last_run_text}</b>",
    )
