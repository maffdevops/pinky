from __future__ import annotations

import logging
import json
from typing import Any

from fastapi import FastAPI, Request, HTTPException, Response
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
    need = (settings.WEBHOOK_SECRET or "").strip()
    if not need:
        # можно оставить пустым на тестах, но лучше всегда ставить
        return
    got = (request.query_params.get("s") or "").strip()
    if got != need:
        raise HTTPException(status_code=403, detail="forbidden")


async def _find_created_order_by_id(order_id: str):
    orders = await repo.get_created_orders(settings.db_path_abs, limit=500)
    return next((o for o in orders if o.id == order_id), None)


async def _find_created_order_by_crypto_invoice(invoice_id: str):
    orders = await repo.get_created_orders(settings.db_path_abs, limit=500)
    return next((o for o in orders if o.provider == "crypto" and str(o.provider_invoice_id) == str(invoice_id)), None)


@app.get("/hooks/health")
async def health():
    return {"ok": True}


@app.post("/hooks/cactus")
async def cactus_hook(request: Request):
    _check_secret(request)

    # Cactus: application/x-www-form-urlencoded: id, order_id, amount
    form = await request.form()
    order_id = str(form.get("order_id") or "").strip()
    amount = str(form.get("amount") or "").strip()

    log.warning("CACTUS_HOOK form=%s", dict(form))

    if not order_id:
        raise HTTPException(status_code=400, detail="order_id missing")

    # по доке: после webhook обязательно проверить статус через get (ACCEPT/WAIT)
    provider = get_provider("cactus")
    st = await provider.check_status(order_id)
    if st != "paid":
        return {"ok": True, "status": st}

    order = await _find_created_order_by_id(order_id)
    if not order:
        return {"ok": True, "status": "already_processed_or_not_found"}

    await fulfill_paid_order(bot, settings, order)
    return {"ok": True, "status": "paid_processed", "amount": amount}


@app.post("/hooks/crypto")
async def crypto_hook(request: Request):
    _check_secret(request)

    raw = await request.body()
    data: dict[str, Any] = {}

    # CryptoBot обычно шлёт JSON, но мы не будем доверять формату — делаем “железно”
    try:
        data = await request.json()
    except Exception:
        try:
            form = await request.form()
            data = dict(form)
        except Exception:
            data = {}

    log.warning("CRYPTO_HOOK raw=%s json=%s", raw.decode("utf-8", "ignore"), json.dumps(data, ensure_ascii=False))

    # 1) пытаемся вытащить invoice_id
    invoice_id = str(
        data.get("invoice_id")
        or data.get("invoiceId")
        or data.get("id")
        or ""
    ).strip()

    # 2) иногда можно получить order_id из payload: "order:<id>"
    payload = str(data.get("payload") or data.get("data") or "").strip()
    order_id_from_payload = ""
    if payload.startswith("order:"):
        order_id_from_payload = payload.split("order:", 1)[1].strip()

    provider = get_provider("crypto")

    # Если есть order_id в payload — попробуем найти order по id
    if order_id_from_payload:
        order = await _find_created_order_by_id(order_id_from_payload)
        if not order:
            return {"ok": True, "status": "already_processed_or_not_found"}

        if not order.provider_invoice_id:
            # на всякий: если вдруг invoice_id не записался
            return {"ok": True, "status": "order_missing_invoice_id"}

        st = await provider.check_status(order.provider_invoice_id)
        if st != "paid":
            return {"ok": True, "status": st}

        await fulfill_paid_order(bot, settings, order)
        return {"ok": True, "status": "paid_processed"}

    # Иначе работаем по invoice_id
    if not invoice_id:
        return {"ok": True, "status": "no_invoice_id"}

    st = await provider.check_status(invoice_id)
    if st != "paid":
        return {"ok": True, "status": st}

    order = await _find_created_order_by_crypto_invoice(invoice_id)
    if not order:
        return {"ok": True, "status": "already_processed_or_not_found"}

    await fulfill_paid_order(bot, settings, order)
    return {"ok": True, "status": "paid_processed"}


@app.head("/hooks/cactus")
@app.head("/hooks/crypto")
async def hook_head():
    return Response(status_code=200)