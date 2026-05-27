from datetime import date

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DateMode
from app.keyboards.inline import (
    airport_results_kb,
    cancel_kb,
    confirm_kb,
    date_mode_kb,
    days_kb,
    months_kb,
    seats_left_badge,
)
from app.ryanair import airports
from app.ryanair.client import RyanairClient
from app.services import subscriptions as sub_svc
from app.services.notifier import Notifier

log = structlog.get_logger(__name__)

router = Router()


class AddSub(StatesGroup):
    origin = State()
    destination = State()
    date_mode = State()
    month_from = State()
    day_from = State()
    month_to = State()
    day_to = State()
    confirm = State()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

async def _enter_add_flow(target: Message | CallbackQuery, state: FSMContext) -> None:
    msg = target if isinstance(target, Message) else target.message
    await state.clear()
    await state.set_state(AddSub.origin)
    await msg.answer(
        "✈️ <b>Step 1 / 4 — Departure airport</b>\n\n"
        "Type a city, airport name, or IATA code:\n"
        "<i>Examples: London, Berlin, STN, DUB</i>",
        reply_markup=cancel_kb(),
    )
    if isinstance(target, CallbackQuery):
        await target.answer()


@router.message(Command("add"))
@router.message(F.text == "➕ Add tracker")
async def cmd_add(message: Message, state: FSMContext) -> None:
    await _enter_add_flow(message, state)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Nothing to cancel.")
        return
    await state.clear()
    await message.answer("❌ Cancelled.")


@router.callback_query(F.data == "add_sub")
async def cb_add_sub(callback: CallbackQuery, state: FSMContext) -> None:
    await _enter_add_flow(callback, state)


# ---------------------------------------------------------------------------
# Origin search & select
# ---------------------------------------------------------------------------

@router.message(AddSub.origin)
async def origin_search(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    matches = airports.search(query)
    if not matches:
        await message.answer(
            "❌ No matching airports found. Try a different city or code:"
        )
        return
    await message.answer(
        f"Found {len(matches)} airport(s) — pick your departure:",
        reply_markup=airport_results_kb(matches, "origin"),
    )


@router.callback_query(AddSub.origin, F.data.startswith("airport_origin:"))
async def origin_select(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    airport = airports.get_airport(code)
    if airport is None:
        await callback.answer("Airport not found, try searching again.", show_alert=True)
        return
    await state.update_data(origin=code)
    await state.set_state(AddSub.destination)
    await callback.message.edit_text(
        f"✅ Departure: <b>{airport.display()}</b>\n\n"
        "✈️ <b>Step 2 / 4 — Destination airport</b>\n\n"
        "Type a city, airport name, or IATA code:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Destination search & select
# ---------------------------------------------------------------------------

@router.message(AddSub.destination)
async def destination_search(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    matches = airports.search(query)
    if not matches:
        await message.answer(
            "❌ No matching airports found. Try a different city or code:"
        )
        return
    await message.answer(
        f"Found {len(matches)} airport(s) — pick your destination:",
        reply_markup=airport_results_kb(matches, "destination"),
    )


@router.callback_query(AddSub.destination, F.data.startswith("airport_destination:"))
async def destination_select(
    callback: CallbackQuery,
    state: FSMContext,
    ryanair_client: RyanairClient,
) -> None:
    code = callback.data.split(":", 1)[1]
    airport = airports.get_airport(code)
    if airport is None:
        await callback.answer("Airport not found, try searching again.", show_alert=True)
        return

    data = await state.get_data()
    origin_code = data["origin"]

    # Validate route exists
    valid_routes = await ryanair_client.get_routes_from(origin_code)
    if valid_routes and code not in valid_routes:
        await callback.answer(
            f"Route {origin_code} → {code} is not served by Ryanair. Try another destination.",
            show_alert=True,
        )
        return

    origin_airport = airports.get_airport(origin_code)
    await state.update_data(destination=code)
    await state.set_state(AddSub.date_mode)
    await callback.message.edit_text(
        f"✅ Route: <b>{origin_airport.display() if origin_airport else origin_code} → {airport.display()}</b>\n\n"
        "📅 <b>Step 3 / 4 — Date mode</b>\n\n"
        "Choose how you want to track this route:",
        reply_markup=date_mode_kb(),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Date mode
# ---------------------------------------------------------------------------

@router.callback_query(AddSub.date_mode, F.data.startswith("mode:"))
async def date_mode_select(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":", 1)[1]
    await state.update_data(mode=mode)
    await state.set_state(AddSub.month_from)
    label = "departure" if mode == "specific" else "start"
    await callback.message.edit_text(
        f"📅 <b>Step 4 / 4 — Pick the {label} month:</b>",
        reply_markup=months_kb("from"),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Month / day — from
# ---------------------------------------------------------------------------

@router.callback_query(AddSub.month_from, F.data.startswith("month_from:"))
async def month_from_select(
    callback: CallbackQuery,
    state: FSMContext,
    ryanair_client: RyanairClient,
) -> None:
    ym = callback.data.split(":", 1)[1]  # "YYYY-MM"
    year, month = int(ym[:4]), int(ym[5:7])
    month_date = date(year, month, 1)

    data = await state.get_data()
    origin, dest = data["origin"], data["destination"]

    await callback.message.edit_text(f"⏳ Loading available days for {month_date.strftime('%B %Y')}…")

    try:
        fares = await ryanair_client.get_cheapest_per_day(origin, dest, month_date)
        today = date.today()
        available = [
            f.day for f in fares.fares
            if f.is_available and f.day >= today
        ]
    except Exception as exc:
        log.error("month_from_fetch_failed", error=str(exc))
        await callback.message.edit_text(
            "⚠️ Could not load fares for that month. Please try another:",
            reply_markup=months_kb("from"),
        )
        await callback.answer()
        return

    if not available:
        await callback.message.edit_text(
            f"No available fares in {month_date.strftime('%B %Y')}. Try another month:",
            reply_markup=months_kb("from"),
        )
        await callback.answer()
        return

    await state.update_data(
        month_from=ym,
        available_from=[d.isoformat() for d in available],
    )
    await state.set_state(AddSub.day_from)
    await callback.message.edit_text(
        f"📅 <b>{month_date.strftime('%B %Y')}</b> — pick a day ({len(available)} available):",
        reply_markup=days_kb(available, "from"),
    )
    await callback.answer()


@router.callback_query(AddSub.day_from, F.data.startswith("day_from:"))
async def day_from_select(callback: CallbackQuery, state: FSMContext) -> None:
    day_str = callback.data.split(":", 1)[1]
    date_from = date.fromisoformat(day_str)
    await state.update_data(date_from=day_str)

    data = await state.get_data()
    if data.get("mode") == "specific":
        await state.update_data(date_to=day_str)
        await state.set_state(AddSub.confirm)
        await _show_confirm(callback.message, await state.get_data())
    else:
        await state.set_state(AddSub.month_to)
        await callback.message.edit_text(
            f"✅ Start date: <b>{date_from.strftime('%d %b %Y')}</b>\n\n"
            "📅 Now pick the <b>end month</b>:",
            reply_markup=months_kb("to", min_month=date_from),
        )
    await callback.answer()


@router.callback_query(AddSub.day_from, F.data == "back_months_from")
async def back_months_from(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddSub.month_from)
    await callback.message.edit_text(
        "📅 Pick the departure month:",
        reply_markup=months_kb("from"),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Month / day — to (range mode only)
# ---------------------------------------------------------------------------

@router.callback_query(AddSub.month_to, F.data.startswith("month_to:"))
async def month_to_select(
    callback: CallbackQuery,
    state: FSMContext,
    ryanair_client: RyanairClient,
) -> None:
    ym = callback.data.split(":", 1)[1]
    year, month = int(ym[:4]), int(ym[5:7])
    month_date = date(year, month, 1)

    data = await state.get_data()
    origin, dest = data["origin"], data["destination"]
    date_from = date.fromisoformat(data["date_from"])

    await callback.message.edit_text(f"⏳ Loading available days for {month_date.strftime('%B %Y')}…")

    try:
        fares = await ryanair_client.get_cheapest_per_day(origin, dest, month_date)
        available = [
            f.day for f in fares.fares
            if f.is_available and f.day >= date_from
        ]
    except Exception as exc:
        log.error("month_to_fetch_failed", error=str(exc))
        await callback.message.edit_text(
            "⚠️ Could not load fares for that month. Please try another:",
            reply_markup=months_kb("to", min_month=date_from),
        )
        await callback.answer()
        return

    if not available:
        await callback.message.edit_text(
            f"No available fares in {month_date.strftime('%B %Y')}. Try another month:",
            reply_markup=months_kb("to", min_month=date_from),
        )
        await callback.answer()
        return

    await state.update_data(
        month_to=ym,
        available_to=[d.isoformat() for d in available],
    )
    await state.set_state(AddSub.day_to)
    await callback.message.edit_text(
        f"📅 <b>{month_date.strftime('%B %Y')}</b> — pick end day ({len(available)} available):",
        reply_markup=days_kb(available, "to"),
    )
    await callback.answer()


@router.callback_query(AddSub.day_to, F.data.startswith("day_to:"))
async def day_to_select(callback: CallbackQuery, state: FSMContext) -> None:
    day_str = callback.data.split(":", 1)[1]
    await state.update_data(date_to=day_str)
    await state.set_state(AddSub.confirm)
    await _show_confirm(callback.message, await state.get_data())
    await callback.answer()


@router.callback_query(AddSub.day_to, F.data == "back_months_to")
async def back_months_to(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    date_from = date.fromisoformat(data["date_from"])
    await state.set_state(AddSub.month_to)
    await callback.message.edit_text(
        "📅 Pick the end month:",
        reply_markup=months_kb("to", min_month=date_from),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------

async def _show_confirm(message: Message, data: dict) -> None:
    origin_ap = airports.get_airport(data["origin"])
    dest_ap = airports.get_airport(data["destination"])
    date_from = date.fromisoformat(data["date_from"])
    date_to = date.fromisoformat(data["date_to"])

    origin_label = origin_ap.display() if origin_ap else data["origin"]
    dest_label = dest_ap.display() if dest_ap else data["destination"]
    date_text = (
        date_from.strftime("%d %b %Y")
        if date_from == date_to
        else f"{date_from.strftime('%d %b %Y')} – {date_to.strftime('%d %b %Y')}"
    )

    await message.edit_text(
        f"📋 <b>Confirm tracker</b>\n\n"
        f"✈️ <b>{origin_label}</b>\n"
        f"    → <b>{dest_label}</b>\n"
        f"📅 {date_text}\n\n"
        "Save this tracker?",
        reply_markup=confirm_kb(),
    )


@router.callback_query(AddSub.confirm, F.data == "confirm:yes")
async def process_confirm_yes(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    ryanair_client: RyanairClient,
    notifier: Notifier,
) -> None:
    data = await state.get_data()
    await state.clear()

    mode = DateMode.SPECIFIC_DAY if data.get("mode") == "specific" else DateMode.DATE_RANGE
    date_from = date.fromisoformat(data["date_from"])
    date_to = date.fromisoformat(data["date_to"])
    origin, dest = data["origin"], data["destination"]

    sub = await sub_svc.create_subscription(
        session,
        user_id=callback.from_user.id,
        origin=origin,
        destination=dest,
        mode=mode,
        date_from=date_from,
        date_to=date_to,
    )

    await callback.message.edit_text("⏳ Tracker saved! Checking current prices…")

    from app.services.price_tracker import check_subscription
    await check_subscription(sub, ryanair_client, {}, session)

    origin_ap = airports.get_airport(origin)
    dest_ap = airports.get_airport(dest)
    date_text = (
        date_from.strftime("%d %b %Y")
        if date_from == date_to
        else f"{date_from.strftime('%d %b %Y')} – {date_to.strftime('%d %b %Y')}"
    )
    price_text = (
        f"\n💰 Current minimum: <b>{sub.best_price} {sub.currency}</b> on {sub.best_price_date.strftime('%d %b %Y')}"
        f"{seats_left_badge(sub.best_price_seats_left)}"
        if sub.best_price
        else "\n⚠️ No fares found yet for this route."
    )

    await callback.message.edit_text(
        f"✅ <b>Tracker active!</b>\n\n"
        f"✈️ {origin_ap.display() if origin_ap else origin}\n"
        f"    → {dest_ap.display() if dest_ap else dest}\n"
        f"📅 {date_text}"
        f"{price_text}",
    )
    await callback.answer("✅ Saved!")

    username = callback.from_user.username or callback.from_user.first_name or str(callback.from_user.id)
    await notifier.notify_admin(
        f"📍 <b>New tracker</b>\n"
        f"@{username} (<code>{callback.from_user.id}</code>)\n"
        f"{origin} → {dest} | {date_text}\n"
        f"Min: {sub.best_price or '—'} {sub.currency}"
    )


@router.callback_query(AddSub.confirm, F.data == "confirm:no")
@router.callback_query(F.data == "cancel")
async def process_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Cancelled.")
    await callback.answer()
