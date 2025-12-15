from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..callbacks import PayMethodCb, MenuCb, ConfirmCb


def pay_method_kb(tariff_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏦 Cactus | РФ | СБП | QR",
                    callback_data=PayMethodCb(provider="cactus", tariff=tariff_code).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🪙 CryptoBot",
                    callback_data=PayMethodCb(provider="crypto", tariff=tariff_code).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=ConfirmCb(action="back").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 В меню",
                    callback_data=MenuCb(action="home").pack(),
                )
            ],
        ]
    )