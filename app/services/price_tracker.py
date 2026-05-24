from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import structlog

from app.db.models import PriceSnapshot, Subscription
from app.db.session import AsyncSessionFactory
from app.ryanair.client import RyanairClient
from app.ryanair.schemas import MonthlyFares

log = structlog.get_logger(__name__)

_last_run: datetime | None = None


def get_last_run() -> datetime | None:
    return _last_run


def _months_in_range(date_from: date, date_to: date) -> list[date]:
    months: list[date] = []
    current = date_from.replace(day=1)
    end = date_to.replace(day=1)
    while current <= end:
        months.append(current)
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return months


async def check_subscription(
    sub: Subscription,
    client: RyanairClient,
    cache: dict[tuple[str, str, str], MonthlyFares],
    session=None,
) -> tuple[Decimal, Decimal] | None:
    """Fetch fares for the subscription window. Returns (new_price, prev_price) on a new minimum, None otherwise."""
    fares_in_window = []

    for month_date in _months_in_range(sub.date_from, sub.date_to):
        cache_key = (sub.origin_iata, sub.destination_iata, month_date.strftime("%Y-%m"))
        if cache_key not in cache:
            try:
                cache[cache_key] = await client.get_cheapest_per_day(
                    sub.origin_iata, sub.destination_iata, month_date, sub.currency
                )
            except Exception as exc:
                log.error(
                    "fare_fetch_failed",
                    origin=sub.origin_iata,
                    dest=sub.destination_iata,
                    month=month_date.strftime("%Y-%m"),
                    error=str(exc),
                )
                continue
        monthly = cache.get(cache_key)
        if monthly:
            fares_in_window.extend(monthly.available_in_range(sub.date_from, sub.date_to))

    if not fares_in_window:
        return None

    cheapest = min(fares_in_window, key=lambda f: f.price.value)  # type: ignore[union-attr]
    min_price: Decimal = cheapest.price.value  # type: ignore[union-attr]
    min_date: date = cheapest.day

    if session:
        session.add(
            PriceSnapshot(
                subscription_id=sub.id,
                min_price=min_price,
                min_price_date=min_date,
                available_count=len(fares_in_window),
            )
        )

    if sub.best_price is None:
        sub.best_price = min_price
        sub.best_price_date = min_date
        sub.best_price_seen_at = datetime.utcnow()
        if session:
            await session.commit()
        return None

    if min_price < sub.best_price:
        prev_best = sub.best_price
        sub.best_price = min_price
        sub.best_price_date = min_date
        sub.best_price_seen_at = datetime.utcnow()
        if session:
            await session.commit()
        log.info(
            "new_best_price",
            sub_id=sub.id,
            prev=str(prev_best),
            new=str(min_price),
            flight_date=str(min_date),
        )
        return (min_price, prev_best)

    if session:
        await session.commit()
    return None


async def run_check(client: RyanairClient, bot, notifier) -> None:
    global _last_run
    log.info("price_check_started")

    from app.ryanair.airports import get_airport
    from app.services.subscriptions import get_all_active

    alerts: list[tuple[int, str]] = []
    subs: list[Subscription] = []

    async with AsyncSessionFactory() as session:
        subs = await get_all_active(session)
        cache: dict[tuple[str, str, str], MonthlyFares] = {}

        for sub in subs:
            try:
                result = await check_subscription(sub, client, cache, session)
                if result is not None:
                    new_price, prev_price = result
                    date_text = (
                        sub.date_from.strftime("%d %b %Y")
                        if sub.date_from == sub.date_to
                        else f"{sub.date_from.strftime('%d %b %Y')} – {sub.date_to.strftime('%d %b %Y')}"
                    )
                    origin_ap = get_airport(sub.origin_iata)
                    dest_ap = get_airport(sub.destination_iata)
                    origin_label = f"{origin_ap.name} ({sub.origin_iata})" if origin_ap else sub.origin_iata
                    dest_label = f"{dest_ap.name} ({sub.destination_iata})" if dest_ap else sub.destination_iata
                    msg = (
                        f"🔥 <b>New lowest price!</b>\n"
                        f"{origin_label} → {dest_label}\n"
                        f"📅 {date_text}\n"
                        f"💰 <b>{new_price} {sub.currency}</b> "
                        f"<i>(was: {prev_price} {sub.currency})</i>\n"
                        f"📆 Flight date: {sub.best_price_date.strftime('%d %b %Y')}"
                    )
                    alerts.append((sub.user_id, msg))
            except Exception as exc:
                log.error("sub_check_failed", sub_id=sub.id, error=str(exc))

    for user_id, msg in alerts:
        await notifier.notify_user(user_id, msg)

    _last_run = datetime.utcnow()
    log.info("price_check_done", alerts_sent=len(alerts), subs_checked=len(subs))
