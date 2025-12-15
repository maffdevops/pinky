from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..callbacks import TariffCb, MenuCb
from ..data_tariffs import TARIFFS


def tariffs_kb() -> InlineKeyboardMarkup:
    t_forever = TARIFFS["forever"]
    t_month = TARIFFS["month"]
    t_week = TARIFFS["week"]
    t_trial = TARIFFS["trial"]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🏆 НАВСЕГДА — {t_forever.price_rub}р",
                    callback_data=TariffCb(code="forever").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🗓️ МЕСЯЦ — {t_month.price_rub}р",
                    callback_data=TariffCb(code="month").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📆 НЕДЕЛЯ — {t_week.price_rub}р",
                    callback_data=TariffCb(code="week").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🧪 ПРОБНИК — {t_trial.price_rub}р",
                    callback_data=TariffCb(code="trial").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Вернуться в меню",
                    callback_data=MenuCb(action="home").pack(),
                )
            ],
        ]
    )