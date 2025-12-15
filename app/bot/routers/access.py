from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ..callbacks import MenuCb, TariffCb, ConfirmCb
from ..keyboards.tariffs import tariffs_kb
from ..keyboards.confirm import confirm_kb
from ..keyboards.pay_method import pay_method_kb
from ..data_tariffs import TARIFFS
from ..utils.message_cleanup import replace_screen


router = Router()


class AccessFlow(StatesGroup):
    choosing_tariff = State()
    confirming = State()
    choosing_pay_method = State()


@router.callback_query(MenuCb.filter(F.action == "access"))
async def show_tariffs(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.clear()
    await state.set_state(AccessFlow.choosing_tariff)

    text = "✨ *Выберите тариф который вас интересует* 👇"
    await replace_screen(
        message=call.message,
        text=text,
        photo_path="assets/images/tariffs.jpg",
        reply_markup=tariffs_kb(),
    )


@router.callback_query(TariffCb.filter())
async def confirm_tariff(call: CallbackQuery, callback_data: TariffCb, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(AccessFlow.confirming)
    await state.update_data(tariff_code=callback_data.code)

    t = TARIFFS[callback_data.code]

    text = (
        "🍩 *Товар:* 🔥 Пpивaтный Кaнaл\n"
        f"💰 *Цена:* {t.price_rub} ₽\n"
        "ℹ️ *Описание:* ➜ Доступ к расширенным папкам! Мнoгo видeо и фoто.\n\n"
        "📁 ℹ️ Расширенные папки.\n"
        "🗂️ ℹ️ Сортировка файлов по папкам.\n"
        "☁️ ℹ️ Папки в облачном хранилище.\n"
        "🆕 ℹ️ Канал регулярно пополняется новыми файлами.\n\n"
        "❓ *Вы действительно хотите купить?*"
    )

    await replace_screen(
        message=call.message,
        text=text,
        photo_path="assets/images/confirm.jpg",
        reply_markup=confirm_kb(),
    )


@router.callback_query(ConfirmCb.filter(F.action == "yes"))
async def confirm_yes(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    data = await state.get_data()
    tariff_code = data.get("tariff_code", "week")

    await state.set_state(AccessFlow.choosing_pay_method)

    text = "💳 *Выберите удобный способ:*"
    await replace_screen(
        message=call.message,
        text=text,
        photo_path="assets/images/pay_method.jpg",
        reply_markup=pay_method_kb(tariff_code),
    )


@router.callback_query(ConfirmCb.filter(F.action.in_(["no", "back"])))
async def confirm_no_or_back(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(AccessFlow.choosing_tariff)

    text = "✨ *Выберите тариф который вас интересует* 👇"
    await replace_screen(
        message=call.message,
        text=text,
        photo_path="assets/images/tariffs.jpg",
        reply_markup=tariffs_kb(),
    )