from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..callbacks import OrderCb, MenuCb


def order_kb(order_id: str, pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=pay_url)],
            [
                InlineKeyboardButton(
                    text="🧯 Отмена оплаты",
                    callback_data=OrderCb(action="cancel", order_id=order_id).pack(),
                )
            ],
            [InlineKeyboardButton(text="🏠 В меню", callback_data=MenuCb(action="home").pack())],
        ]
    )