from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot

from ..config import Settings
from ..db import repo
from ..services.payments.factory import get_provider
from ..services.access.invites import kick_user
from ..services.payments.fulfill import fulfill_paid_order

log = logging.getLogger(__name__)

PAYMENTS_POLL_SECONDS = 10
EXPIRE_POLL_SECONDS = 20
SUBS_EXPIRE_POLL_SECONDS = 30


def start_background_jobs(dp, bot: Bot, settings: Settings) -> None:
    asyncio.create_task(_payments_loop(bot, settings))
    asyncio.create_task(_expire_orders_loop(settings))
    asyncio.create_task(_expire_subscriptions_loop(bot, settings))


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
                    await fulfill_paid_order(bot, settings, o)

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