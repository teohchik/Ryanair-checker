from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.inline import (
    format_history_text,
    format_subscriptions_text,
    history_back_kb,
    subscriptions_kb,
)
from app.services import subscriptions as sub_svc
from app.services.price_tracker import get_last_run

router = Router()


@router.message(Command("my"))
@router.message(F.text == "📋 My trackers")
async def cmd_my(message: Message, session: AsyncSession) -> None:
    subs = await sub_svc.get_user_subscriptions(session, message.from_user.id)
    if not subs:
        await message.answer("You have no active trackers yet.")
        return
    last_run = get_last_run()
    last_run_text = (
        f"\n\n🕐 <i>Last price check: {last_run.strftime('%d %b %Y, %H:%M')} UTC</i>"
        if last_run
        else "\n\n🕐 <i>Price check: not run yet since bot start</i>"
    )
    await message.answer(
        format_subscriptions_text(subs) + last_run_text,
        reply_markup=subscriptions_kb(subs),
    )


@router.callback_query(F.data == "list_subs")
async def cb_list_subs(callback: CallbackQuery, session: AsyncSession) -> None:
    subs = await sub_svc.get_user_subscriptions(session, callback.from_user.id)
    if not subs:
        await callback.message.edit_text("You have no active trackers yet.")
    else:
        await callback.message.edit_text(
            format_subscriptions_text(subs),
            reply_markup=subscriptions_kb(subs),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("del_sub:"))
async def cb_delete_sub(callback: CallbackQuery, session: AsyncSession) -> None:
    sub_id = int(callback.data.split(":")[1])
    deleted = await sub_svc.deactivate_subscription(session, sub_id, callback.from_user.id)
    if not deleted:
        await callback.answer("Tracker not found or already removed.", show_alert=True)
        return
    await callback.answer("✅ Tracker removed!")
    subs = await sub_svc.get_user_subscriptions(session, callback.from_user.id)
    if not subs:
        await callback.message.edit_text("✅ Tracker removed. You have no active trackers.")
    else:
        await callback.message.edit_text(
            f"✅ Tracker removed.\n\n{format_subscriptions_text(subs)}",
            reply_markup=subscriptions_kb(subs),
        )


@router.callback_query(F.data.startswith("hist_sub:"))
async def cb_history(callback: CallbackQuery, session: AsyncSession) -> None:
    sub_id = int(callback.data.split(":")[1])
    sub = await sub_svc.get_subscription(session, sub_id, callback.from_user.id)
    if sub is None:
        await callback.answer("Tracker not found.", show_alert=True)
        return
    snapshots = await sub_svc.get_recent_snapshots(session, sub_id)
    stats = await sub_svc.get_price_stats(session, sub_id)
    await callback.message.edit_text(
        format_history_text(sub, snapshots, stats),
        reply_markup=history_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub_info:"))
async def cb_sub_info(callback: CallbackQuery) -> None:
    await callback.answer("Press 🗑 Remove to delete this tracker", show_alert=False)
