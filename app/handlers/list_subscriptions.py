from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.inline import format_subscriptions_text, main_menu_kb, subscriptions_kb
from app.services import subscriptions as sub_svc

router = Router()


@router.message(Command("my"))
async def cmd_my(message: Message, session: AsyncSession) -> None:
    subs = await sub_svc.get_user_subscriptions(session, message.from_user.id)
    if not subs:
        await message.answer(
            "You have no active trackers yet.",
            reply_markup=main_menu_kb(),
        )
        return
    await message.answer(
        format_subscriptions_text(subs),
        reply_markup=subscriptions_kb(subs),
    )


@router.callback_query(F.data == "list_subs")
async def cb_list_subs(callback: CallbackQuery, session: AsyncSession) -> None:
    subs = await sub_svc.get_user_subscriptions(session, callback.from_user.id)
    if not subs:
        await callback.message.edit_text(
            "You have no active trackers yet.",
            reply_markup=main_menu_kb(),
        )
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
        await callback.message.edit_text(
            "✅ Tracker removed. You have no active trackers.",
            reply_markup=main_menu_kb(),
        )
    else:
        await callback.message.edit_text(
            f"✅ Tracker removed.\n\n{format_subscriptions_text(subs)}",
            reply_markup=subscriptions_kb(subs),
        )


@router.callback_query(F.data.startswith("sub_info:"))
async def cb_sub_info(callback: CallbackQuery) -> None:
    await callback.answer("Press 🗑 Remove to delete this tracker", show_alert=False)
