from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_ADD = "➕ Add tracker"
BTN_MY = "📋 My trackers"
BTN_HELP = "❓ Help"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADD), KeyboardButton(text=BTN_MY)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
