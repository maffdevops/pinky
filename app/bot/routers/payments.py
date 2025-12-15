from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.types import CallbackQuery

from ..callbacks import PayMethodCb, OrderCb, MenuCb
from ..data_tariffs import TARIFFS
from ..keyboards.order import order_kb
from ..utils.message_cleanup import replace_screen
from ..config import Settings

from ..services.payments.factory import get_provider
from ..services.orders import create_order, cancel_order, attach_invoice


router = Router()


def _provider_title(provider: str) -> str:
    if provider == "cactus":
        return "CACTUS_PAY"
    if provider == "crypto":
        return "CRYPTO_BOT"
    return provider.upper()


def _format_pay_until_msk(pay_until: str) -> str | None:
    """
    pay_until пример: 'Wed, 12 Feb 2025 22:50:52 +0300'
    Выводим: '2025-02-12 22:50 (МСК)' или '06:23 (МСК)' — сделаем 'HH:MM (МСК)'.
    """
    try:
        dt = parsedate_to_datetime(pay_until)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        msk = dt.astimezone(ZoneInfo("Europe/Moscow"))
        return msk.strftime("%H:%M (МСК)")
    except Exception:
        return None


@router.callback_query(PayMethodCb.filter())
async def start_payment(call: CallbackQuery, callback_data: PayMethodCb) -> None:
    await call.answer()
    settings = Settings()

    tariff = TARIFFS[callback_data.tariff]

    order = await create_order(
        user_id=call.from_user.id,
        tariff_code=tariff.code,
        price_rub=tariff.price_rub,
        provider=callback_data.provider,
    )

    provider = get_provider(callback_data.provider)
    invoice = await provider.create_invoice(order_id=order.id, amount_rub=order.price_rub)

    await attach_invoice(order.id, provider_invoice_id=invoice.invoice_id, pay_url=invoice.pay_url)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    deadline_line = ""
    if invoice.pay_until:
        nice = _format_pay_until_msk(invoice.pay_until)
        if nice:
            deadline_line = f"🕜 *Необходимо оплатить до:* {nice}\n"
        else:
            deadline_line = f"🕜 *Необходимо оплатить до:* {invoice.pay_until}\n"

    qr_line = ""
    if invoice.receiver_qr:
        qr_line = f"🔳 *QR (СБП):* {invoice.receiver_qr}\n"

    text = (
        "➖➖➖➖➖➖➖➖➖➖➖➖\n"
        "📃 *Товар:* 🔥 Пpивaтный Кaнaл\n"
        f"💰 *Цена:* {order.price_rub} ₽\n"
        "📦 *Кол-во:* 1 шт.\n"
        f"💡 *Заказ:* {order.id}\n"
        f"🕐 *Время заказа:* {now_str}\n"
        f"🧾 *Итоговая сумма:* {order.price_rub} ₽\n"
        f"💲 *Способ оплаты:* {_provider_title(callback_data.provider)}\n"
        "➖➖➖➖➖➖➖➖➖➖➖➖\n\n"
        "➖➖➖➖➖➖➖➖➖\n"
        "⚙️ *Стабильная работа,* рекомендуем использовать этот платежный инструмент.\n"
        "➖➖➖➖➖➖➖➖➖\n\n"
        "💳 *Оплата:* Перевод (СБП/QR) или CryptoBot — зависит от выбранного способа.\n"
        "➖➖➖➖➖➖➖➖➖\n"
        "⏰ *Время на оплату:* 10 минут\n"
        f"{deadline_line}{qr_line}"
        "➖➖➖➖➖➖➖➖➖➖➖➖"
    )

    await replace_screen(
        message=call.message,
        text=text,
        photo_path="assets/images/payment.jpg",
        reply_markup=order_kb(order.id, invoice.pay_url),
    )


@router.callback_query(OrderCb.filter())
async def order_actions(call: CallbackQuery, callback_data: OrderCb) -> None:
    await call.answer()

    if callback_data.action == "cancel":
        await cancel_order(callback_data.order_id)
        text = "🧯 *Оплата отменена.*\n\n🏠 Возвращаем в меню."
        await replace_screen(
            message=call.message,
            text=text,
            photo_path="assets/images/main_menu.jpg",
            reply_markup=None,
        )


@router.callback_query(MenuCb.filter())
async def menu_fallback(call: CallbackQuery) -> None:
    await call.answer()