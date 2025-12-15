from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

from ..config import Settings
from ..db import repo
from ..data_tariffs import TARIFFS
from ..services.payments.factory import get_provider
from ..services.access.invites import create_one_time_invite, kick_user
from ..callbacks import MenuCb

log = logging.getLogger(__name__)

PAYMENTS_POLL_SECONDS = 10
EXPIRE_POLL_SECONDS = 20
SUBS_EXPIRE_POLL_SECONDS = 30


def start_background_jobs(dp, bot: Bot, settings: Settings) -> None:
    asyncio.create_task(_payments_loop(bot, settings))
    asyncio.create_task(_expire_orders_loop(settings))
    asyncio.create_task(_expire_subscriptions_loop(bot, settings))


def _fmt_local(settings: Settings, iso_utc_naive: str) -> str:
    """
    Мы храним время в БД как naive ISO, но считаем что это UTC.
    Отображаем в TIMEZONE (по умолчанию Europe/Moscow).
    """
    tz = ZoneInfo(settings.TIMEZONE)
    dt = datetime.fromisoformat(iso_utc_naive).replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


async def _send_screen(
    bot: Bot,
    settings: Settings,
    user_id: int,
    text: str,
    *,
    photo_path: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
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
        sent = await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )

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


async def _payments_loop(bot: Bot, settings: Settings) -> None:
    while True:
        try:
            orders = await repo.get_created_orders(settings.db_path_abs, limit=100)

            for o in orders:
                if not o.provider_invoice_id:
                    continue

                provider = get_provider(o.provider)
                status = await provider.check_status(o.provider_invoice_id)

                if status == "paid":
                    await repo.mark_order_paid(settings.db_path_abs, o.id)

                    now_utc = datetime.utcnow()  # naive, считаем UTC
                    tariff = TARIFFS.get(o.tariff_code)
                    if not tariff:
                        log.warning("Unknown tariff_code=%s for order=%s", o.tariff_code, o.id)
                        continue

                    ends_at_iso = None
                    if tariff.duration is not None:
                        ends_at_iso = (now_utc + tariff.duration).isoformat()

                    sub = await repo.create_subscription(
                        db_path=settings.db_path_abs,
                        user_id=o.user_id,
                        tariff_code=o.tariff_code,
                        starts_at_iso=now_utc.isoformat(),
                        ends_at_iso=ends_at_iso,
                        order_id=o.id,
                        status="active",
                    )

                    invite = await create_one_time_invite(
                        bot,
                        settings.TARGET_CHAT_ID,
                        ttl_minutes=60,
                        name=f"🔑 Доступ по заказу {o.id}",
                    )

                    if ends_at_iso:
                        period_line = f"⏳ *Доступ до (МСК):* {_fmt_local(settings, ends_at_iso)}\n"
                    else:
                        period_line = "🏆 *Доступ:* НАВСЕГДА\n"

                    user_text = (
                        "✅ *Оплата прошла успешно!*\n\n"
                        f"🧾 *Заказ:* {o.id}\n"
                        f"💰 *Сумма:* {o.price_rub}₽\n"
                        f"🏷️ *Тариф:* {o.tariff_code}\n"
                        f"{period_line}\n"
                        "👇 Нажмите кнопку ниже, чтобы войти:\n"
                        "⚠️ Если вы выйдете — потребуется повторная оплата."
                    )

                    try:
                        await _send_screen(
                            bot,
                            settings,
                            o.user_id,
                            user_text,
                            photo_path="assets/images/success.jpg",
                            reply_markup=_join_kb(invite.url),
                        )
                    except Exception:
                        log.exception("Failed to send paid screen to user %s for order %s", o.user_id, o.id)

                    for admin_id in settings.admin_ids:
                        try:
                            await bot.send_message(
                                admin_id,
                                (
                                    "✅ *Оплата получена!*\n\n"
                                    f"👤 *User ID:* {o.user_id}\n"
                                    f"🧾 *Заказ:* {o.id}\n"
                                    f"💰 *Сумма:* {o.price_rub}₽\n"
                                    f"🏷️ *Тариф:* {o.tariff_code}\n"
                                    f"💳 *Провайдер:* {o.provider.upper()}\n"
                                    f"📌 *Subscription:* {sub.id}\n"
                                ),
                            )
                        except Exception:
                            log.exception("Failed to notify admin %s about paid order %s", admin_id, o.id)

                elif status in ("expired", "canceled"):
                    await repo.set_order_status(settings.db_path_abs, o.id, status)

        except Exception:
            log.exception("payments loop error")

        await asyncio.sleep(PAYMENTS_POLL_SECONDS)


async def _expire_orders_loop(settings: Settings) -> None:
    while True:
        try:
            now_iso = datetime.utcnow().isoformat()
            expired = await repo.get_expired_created_orders(settings.db_path_abs, now_iso)

            for o in expired:
                if o.provider_invoice_id:
                    try:
                        provider = get_provider(o.provider)
                        await provider.cancel(o.provider_invoice_id)
                    except Exception:
                        log.exception("Failed to cancel invoice %s for order %s", o.provider_invoice_id, o.id)

                await repo.set_order_status(settings.db_path_abs, o.id, "expired")

        except Exception:
            log.exception("expire orders loop error")

        await asyncio.sleep(EXPIRE_POLL_SECONDS)


async def _expire_subscriptions_loop(bot: Bot, settings: Settings) -> None:
    while True:
        try:
            now_iso = datetime.utcnow().isoformat()
            due = await repo.get_due_subscriptions_to_expire(settings.db_path_abs, now_iso, limit=200)

            for s in due:
                await kick_user(bot, settings.TARGET_CHAT_ID, s.user_id)
                await repo.set_subscription_status(settings.db_path_abs, s.id, "expired")

                try:
                    await bot.send_message(
                        s.user_id,
                        "⛔️ *Срок подписки закончился.*\n\n🔁 Для доступа нужна повторная оплата через бота.",
                    )
                except Exception:
                    log.exception("Failed to notify user %s about subscription expire %s", s.user_id, s.id)

        except Exception:
            log.exception("expire subscriptions loop error")

        await asyncio.sleep(SUBS_EXPIRE_POLL_SECONDS)