from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DateMode, Subscription


async def create_subscription(
    session: AsyncSession,
    user_id: int,
    origin: str,
    destination: str,
    mode: DateMode,
    date_from: date,
    date_to: date,
    currency: str = "EUR",
) -> Subscription:
    sub = Subscription(
        user_id=user_id,
        origin_iata=origin.upper(),
        destination_iata=destination.upper(),
        mode=mode,
        date_from=date_from,
        date_to=date_to,
        currency=currency,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


async def get_user_subscriptions(session: AsyncSession, user_id: int) -> list[Subscription]:
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


async def deactivate_subscription(
    session: AsyncSession, sub_id: int, user_id: int
) -> bool:
    result = await session.execute(
        select(Subscription).where(
            Subscription.id == sub_id,
            Subscription.user_id == user_id,
            Subscription.is_active.is_(True),
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return False
    sub.is_active = False
    await session.commit()
    return True


async def get_all_active(session: AsyncSession) -> list[Subscription]:
    result = await session.execute(
        select(Subscription).where(Subscription.is_active.is_(True))
    )
    return list(result.scalars().all())
