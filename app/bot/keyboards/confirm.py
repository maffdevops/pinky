from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..callbacks import ConfirmCb


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтверждаю",
                    callback_data=ConfirmCb(action="yes").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=ConfirmCb(action="no").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=ConfirmCb(action="back").pack(),
                )
            ],
        ]
    )