from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import Subscription
from app.ryanair.airports import Airport



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
    """One delete button per tracker (numbered)."""
    builder = InlineKeyboardBuilder()
    for i, sub in enumerate(subs, start=1):
        builder.row(
            InlineKeyboardButton(
                text=f"🗑 Remove #{i}  ({sub.origin_iata} → {sub.destination_iata})",
                callback_data=f"del_sub:{sub.id}",
            )
        )
    return builder.as_markup()


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
        lines.append(
            f"\n<b>#{i}</b>  ✈️ {sub.origin_iata} → {sub.destination_iata}\n"
            f"     📅 {date_text}\n"
            f"     💰 min {price_text}"
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
