from __future__ import annotations

import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from ...config import Settings
from ...db import repo
from ...data_tariffs import TARIFFS
from ..access.invites import create_one_time_invite
from ...callbacks import MenuCb

log = logging.getLogger(__name__)


async def _send_screen(bot: Bot, settings: Settings, user_id: int, text: str, *, photo_path: str | None = None,
                       reply_markup: InlineKeyboardMarkup | None = None) -> None:
    # delete last screen
    try:
        last_chat_id, last_msg_id = await repo.get_last_screen(settings.db_path_abs, user_id)
        if last_chat_id and last_msg_id:
            await bot.delete_message(chat_id=last_chat_id, message_id=last_msg_id)
    except Exception:
        pass

    abs_photo_path = settings.assets_path(photo_path) if photo_path else None

    if abs_photo_path and os.path.exists(abs_photo_path):
        sent = await bot.send_photo(
            chat_id=user_id,
            photo=FSInputFile(abs_photo_path),
            caption=text,
            reply_markup=reply_markup,
        )
    else:
        sent = await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)

    try:
        await repo.set_last_screen(settings.db_path_abs, user_id, sent.chat.id, sent.message_id)
    except Exception:
        pass


def _join_kb(invite_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Войти в канал/группу", url=invite_url)],
            [InlineKeyboardButton(text="🏠 В меню", callback_data=MenuCb(action="home").pack())],
        ]
    )


def _fmt_local(settings: Settings, iso_utc_naive: str) -> str:
    tz = ZoneInfo(settings.TIMEZONE)
    dt = datetime.fromisoformat(iso_utc_naive).replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


async def fulfill_paid_order(bot: Bot, settings: Settings, order) -> None:
    """
    order — объект из repo.get_created_orders()
    Делает всё: mark paid -> subscription -> invite -> сообщение пользователю + админу
    """
    await repo.mark_order_paid(settings.db_path_abs, order.id)

    now_utc = datetime.utcnow()
    tariff = TARIFFS.get(order.tariff_code)
    if not tariff:
        log.warning("Unknown tariff_code=%s for order=%s", order.tariff_code, order.id)
        return

    ends_at_iso = None
    if tariff.duration is not None:
        ends_at_iso = (now_utc + tariff.duration).isoformat()

    sub = await repo.create_subscription(
        db_path=settings.db_path_abs,
        user_id=order.user_id,
        tariff_code=order.tariff_code,
        starts_at_iso=now_utc.isoformat(),
        ends_at_iso=ends_at_iso,
        order_id=order.id,
        status="active",
    )

    invite = await create_one_time_invite(
        bot,
        settings.TARGET_CHAT_ID,
        ttl_minutes=60,
        name=f"🔑 Доступ по заказу {order.id}",
    )

    if ends_at_iso:
        period_line = f"⏳ *Доступ до (МСК):* {_fmt_local(settings, ends_at_iso)}\n"
    else:
        period_line = "🏆 *Доступ:* НАВСЕГДА\n"

    user_text = (
        "✅ *Оплата прошла успешно!*\n\n"
        f"🧾 *Заказ:* {order.id}\n"
        f"💰 *Сумма:* {order.price_rub}₽\n"
        f"🏷️ *Тариф:* {order.tariff_code}\n"
        f"{period_line}\n"
        "👇 Нажмите кнопку ниже, чтобы войти:\n"
        "⚠️ Если вы выйдете — потребуется повторная оплата."
    )

    await _send_screen(
        bot,
        settings,
        order.user_id,
        user_text,
        photo_path="assets/images/success.jpg",
        reply_markup=_join_kb(invite.url),
    )

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                (
                    "✅ *Оплата получена!*\n\n"
                    f"👤 *User ID:* {order.user_id}\n"
                    f"🧾 *Заказ:* {order.id}\n"
                    f"💰 *Сумма:* {order.price_rub}₽\n"
                    f"🏷️ *Тариф:* {order.tariff_code}\n"
                    f"💳 *Провайдер:* {order.provider.upper()}\n"
                    f"📌 *Subscription:* {sub.id}\n"
                ),
            )
        except Exception:
            log.exception("Failed to notify admin %s about paid order %s", admin_id, order.id)