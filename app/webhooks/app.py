from __future__ import annotations

import logging
import json

from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from app.bot.config import Settings
from app.bot.db import repo
from app.bot.services.payments.factory import get_provider
from app.bot.services.payments.fulfill import fulfill_paid_order

log = logging.getLogger("webhooks")
app = FastAPI()

settings = Settings()
bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))


def _check_secret(request: Request) -> None:
    need = (settings.__dict__.get("WEBHOOK_SECRET") or "").strip()  # если нет поля — будет пусто
    got = request.query_params.get("s", "")
    if need and got != need:
        raise HTTPException(status_code=403, detail="forbidden")


@app.get("/hooks/health")
async def health():
    return {"ok": True}


@app.post("/hooks/cactus")
async def cactus_hook(request: Request):
    _check_secret(request)

    # cactus webhook: application/x-www-form-urlencoded
    form = await request.form()
    order_id = str(form.get("order_id") or "").strip()

    if not order_id:
        raise HTTPException(status_code=400, detail="order_id missing")

    # по доке: после webhook нужно проверить статус через /get => ACCEPT / WAIT
    provider = get_provider("cactus")
    status = await provider.check_status(order_id)

    if status != "paid":
        return {"ok": True, "status": status}

    # найти заказ среди created и выполнить выдачу
    orders = await repo.get_created_orders(settings.db_path_abs, limit=500)
    order = next((o for o in orders if o.id == order_id), None)
    if not order:
        # уже обработан или не существует
        return {"ok": True, "status": "already_processed_or_not_found"}

    await fulfill_paid_order(bot, settings, order)
    return {"ok": True, "status": "paid_processed"}


@app.post("/hooks/crypto")
async def crypto_hook(request: Request):
    _check_secret(request)

    # формат может быть разный — логируем, достаем invoice_id где возможно
    raw = await request.body()
    try:
        data = await request.json()
    except Exception:
        data = {}

    log.warning("CRYPTO_HOOK body=%s json=%s", raw.decode("utf-8", "ignore"), json.dumps(data, ensure_ascii=False))

    invoice_id = (
        str(data.get("invoice_id") or data.get("invoiceId") or data.get("id") or "").strip()
    )
    if not invoice_id:
        # если не пришёл invoice_id — просто ок (не падаем)
        return {"ok": True, "status": "no_invoice_id"}

    provider = get_provider("crypto")
    status = await provider.check_status(invoice_id)
    if status != "paid":
        return {"ok": True, "status": status}

    orders = await repo.get_created_orders(settings.db_path_abs, limit=500)
    order = next((o for o in orders if (o.provider == "crypto" and str(o.provider_invoice_id) == str(invoice_id))), None)
    if not order:
        return {"ok": True, "status": "already_processed_or_not_found"}

    await fulfill_paid_order(bot, settings, order)
    return {"ok": True, "status": "paid_processed"}