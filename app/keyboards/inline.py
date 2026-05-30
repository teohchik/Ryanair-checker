from datetime import date
from decimal import Decimal

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import PriceSnapshot, Subscription
from app.ryanair.airports import Airport



def seats_left_badge(seats: int | None, *, compact: bool = False) -> str:
    """Returns urgency badge when fewer than 5 seats remain at the best price."""
    if seats is None or seats >= 5:
        return ""
    if compact:
        return f"  🔥 {seats} left"
    return f"\n🔥 Only {seats} seat(s) left at this price!"


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Cancel", callback_data="cancel")
    return builder.as_markup()


def date_mode_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Specific day", callback_data="mode:specific"))
    builder.row(InlineKeyboardButton(text="📆 Date range", callback_data="mode:range"))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Save", callback_data="confirm:yes")
    builder.button(text="❌ Cancel", callback_data="confirm:no")
    builder.adjust(2)
    return builder.as_markup()


def subscriptions_kb(subs: list[Subscription]) -> InlineKeyboardMarkup:
    """History + remove buttons per tracker, two per row."""
    builder = InlineKeyboardBuilder()
    for i, sub in enumerate(subs, start=1):
        builder.row(
            InlineKeyboardButton(text=f"📈 History #{i}", callback_data=f"hist_sub:{sub.id}"),
            InlineKeyboardButton(
                text=f"🗑 Remove #{i}  ({sub.origin_iata} → {sub.destination_iata})",
                callback_data=f"del_sub:{sub.id}",
            ),
        )
    return builder.as_markup()


def history_back_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀ Back to list", callback_data="list_subs")
    return builder.as_markup()


def format_history_text(
    sub: Subscription,
    snapshots: list[PriceSnapshot],
    stats: tuple[Decimal | None, Decimal | None, Decimal | None, int],
) -> str:
    """Renders the price history view for a single tracker."""
    date_text = (
        sub.date_from.strftime("%d %b %Y")
        if sub.date_from == sub.date_to
        else f"{sub.date_from.strftime('%d %b %Y')} – {sub.date_to.strftime('%d %b %Y')}"
    )
    lines = [
        f"📈 <b>Price history</b>\n"
        f"✈️ {sub.origin_iata} → {sub.destination_iata}  |  📅 {date_text}"
    ]

    low, high, avg, count = stats
    if count > 0:
        lines.append(
            f"\n📉 Lowest <b>{low} {sub.currency}</b>  ·  "
            f"📈 Highest <b>{high} {sub.currency}</b>  ·  "
            f"⌀ Avg <b>{avg} {sub.currency}</b>  ·  {count} checks"
        )

    if not snapshots:
        lines.append("\n<i>No price history yet — first check runs within the next cycle.</i>")
        return "\n".join(lines)

    lines.append("\n<b>Recent checks</b> (newest first):")
    for idx, snap in enumerate(snapshots):
        if snap.min_price is None:
            continue
        # Compare to the next-older snapshot for the trend arrow
        if idx + 1 < len(snapshots) and snapshots[idx + 1].min_price is not None:
            older_price = snapshots[idx + 1].min_price
            if snap.min_price < older_price:
                arrow = "↘️"
            elif snap.min_price > older_price:
                arrow = "↗️"
            else:
                arrow = "➡️"
        else:
            arrow = ""
        ts = snap.checked_at.strftime("%d %b, %H:%M")
        lines.append(f"  {ts} UTC — <b>{snap.min_price} {sub.currency}</b> {arrow}")

    return "\n".join(lines)


def format_subscriptions_text(subs: list[Subscription]) -> str:
    """Renders the full tracker list as message text."""
    lines = [f"📋 <b>Your trackers</b> ({len(subs)}):"]
    for i, sub in enumerate(subs, start=1):
        date_text = (
            sub.date_from.strftime("%d %b %Y")
            if sub.date_from == sub.date_to
            else f"{sub.date_from.strftime('%d %b %Y')} – {sub.date_to.strftime('%d %b %Y')}"
        )
        price_text = f"{sub.best_price} {sub.currency}" if sub.best_price else "not checked yet"
        badge = seats_left_badge(sub.best_price_seats_left, compact=True) if sub.best_price else ""
        now_line = (
            f"\n     📊 now {sub.current_price} {sub.currency}"
            if sub.current_price is not None
            else ""
        )
        lines.append(
            f"\n<b>#{i}</b>  ✈️ {sub.origin_iata} → {sub.destination_iata}\n"
            f"     📅 {date_text}\n"
            f"     💰 min {price_text}{badge}"
            f"{now_line}"
        )
    return "\n".join(lines)


def airport_results_kb(matches: list[Airport], purpose: str) -> InlineKeyboardMarkup:
    """Shows up to 8 airport suggestions. purpose ∈ {'origin', 'destination'}."""
    builder = InlineKeyboardBuilder()
    for a in matches:
        builder.row(
            InlineKeyboardButton(
                text=a.display(),
                callback_data=f"airport_{purpose}:{a.code}",
            )
        )
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
    return builder.as_markup()


def months_kb(purpose: str, min_month: date | None = None) -> InlineKeyboardMarkup:
    """Next 6 months from today (or min_month), 3 per row. purpose ∈ {'from', 'to'}."""
    builder = InlineKeyboardBuilder()
    start = date.today().replace(day=1)
    if min_month:
        start = max(start, min_month.replace(day=1))

    months: list[date] = []
    current = start
    for _ in range(6):
        months.append(current)
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    buttons = [
        InlineKeyboardButton(
            text=m.strftime("%b %Y"),
            callback_data=f"month_{purpose}:{m.strftime('%Y-%m')}",
        )
        for m in months
    ]
    builder.add(*buttons)
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
    return builder.as_markup()


def days_kb(available_days: list[date], purpose: str) -> InlineKeyboardMarkup:
    """Day-number buttons for available days only, 7 per row. purpose ∈ {'from', 'to'}."""
    builder = InlineKeyboardBuilder()
    buttons = [
        InlineKeyboardButton(
            text=str(d.day),
            callback_data=f"day_{purpose}:{d.isoformat()}",
        )
        for d in sorted(available_days)
    ]
    builder.add(*buttons)
    builder.adjust(7)
    builder.row(InlineKeyboardButton(text="◀ Back to months", callback_data=f"back_months_{purpose}"))
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"))
    return builder.as_markup()
