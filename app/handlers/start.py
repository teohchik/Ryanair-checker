from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards.inline import main_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = (message.from_user.first_name or "there") if message.from_user else "there"
    await message.answer(
        f"👋 Hi, {name}!\n\n"
        "I track <b>Ryanair</b> flight prices and notify you when a new lowest price appears.\n\n"
        "<b>What you can do:</b>\n"
        "• ➕ Add a route to track\n"
        "• 📋 View your active trackers\n"
        "• ❌ Remove a tracker",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📖 <b>How to use:</b>\n\n"
        "1️⃣ Press <b>Add tracker</b> or type /add\n"
        "2️⃣ Type a city or airport name (e.g. <code>London</code>, <code>STN</code>)\n"
        "3️⃣ Pick the airport from the list\n"
        "4️⃣ Do the same for the destination\n"
        "5️⃣ Choose tracking mode — specific day or a date range\n"
        "6️⃣ Select a month, then a day (only days with available fares are shown)\n\n"
        "The bot checks prices every 6 hours and notifies you when a new minimum is found.\n\n"
        "📋 <b>Commands:</b>\n"
        "/start — main menu\n"
        "/add — add a tracker\n"
        "/my — my trackers\n"
        "/help — this help message",
    )
