from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DateMode, PriceSnapshot, Subscription


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
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.is_active.is_(True),
        )
        .order_by(Subscription.id)
    )
    return list(result.unique().scalars().all())


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


async def get_subscription(
    session: AsyncSession, sub_id: int, user_id: int
) -> Subscription | None:
    """Return an active subscription owned by user_id, or None."""
    result = await session.execute(
        select(Subscription).where(
            Subscription.id == sub_id,
            Subscription.user_id == user_id,
            Subscription.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def get_recent_snapshots(
    session: AsyncSession, sub_id: int, limit: int = 10
) -> list[PriceSnapshot]:
    """Return the most recent price snapshots for a subscription, newest first."""
    result = await session.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.subscription_id == sub_id)
        .order_by(PriceSnapshot.checked_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_price_stats(
    session: AsyncSession, sub_id: int
) -> tuple[Decimal | None, Decimal | None, Decimal | None, int]:
    """Return (min, max, avg, count) over all snapshots for a subscription."""
    row = await session.execute(
        select(
            func.min(PriceSnapshot.min_price),
            func.max(PriceSnapshot.min_price),
            func.avg(PriceSnapshot.min_price),
            func.count(),
        ).where(PriceSnapshot.subscription_id == sub_id)
    )
    result = row.one()
    low, high, avg, count = result
    return (
        Decimal(str(low)).quantize(Decimal("0.01")) if low is not None else None,
        Decimal(str(high)).quantize(Decimal("0.01")) if high is not None else None,
        Decimal(str(avg)).quantize(Decimal("0.01")) if avg is not None else None,
        count,
    )


async def get_all_active(session: AsyncSession) -> list[Subscription]:
    result = await session.execute(
        select(Subscription)
        .where(Subscription.is_active.is_(True))
        .order_by(Subscription.id)
    )
    return list(result.unique().scalars().all())
