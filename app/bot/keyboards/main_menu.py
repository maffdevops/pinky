from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..callbacks import MenuCb


def main_menu_kb(manager_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔐 Доступы",
                    callback_data=MenuCb(action="access").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="👩🏻‍💻 Связь с менеджером",
                    url=manager_url,
                )
            ],
        ]
    )