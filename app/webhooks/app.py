from __future__ import annotations

import json
import logging
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
    """
    Защита от "подделок": в URL должен быть ?s=<WEBHOOK_SECRET>
    Если WEBHOOK_SECRET пустой — проверку пропускаем (но лучше не оставлять пустым).
    """
    need = (getattr(settings, "WEBHOOK_SECRET", "") or "").strip()
    if not need:
        return
    got = (request.query_params.get("s") or "").strip()
    if got != need:
        raise HTTPException(status_code=403, detail="forbidden")


async def _find_created_order_by_id(order_id: str):
    orders = await repo.get_created_orders(settings.db_path_abs, limit=500)
    return next((o for o in orders if str(o.id) == str(order_id)), None)


async def _find_created_order_by_crypto_invoice(invoice_id: str):
    orders = await repo.get_created_orders(settings.db_path_abs, limit=500)
    return next(
        (o for o in orders if o.provider == "crypto" and str(o.provider_invoice_id) == str(invoice_id)),
        None,
    )


@app.get("/hooks/health")
async def health():
    return {"ok": True}


# --- Чтобы платежки могли "проверить URL" (CryptoBot часто делает GET) ---
@app.get("/hooks/crypto")
@app.get("/hooks/cactus")
async def hook_get(request: Request):
    _check_secret(request)
    return {"ok": True}


@app.head("/hooks/crypto")
@app.head("/hooks/cactus")
async def hook_head():
    return Response(status_code=200)


# -------------------- CACTUS --------------------
@app.post("/hooks/cactus")
async def cactus_hook(request: Request):
    _check_secret(request)

    # По доке: webhook приходит application/x-www-form-urlencoded
    # id, order_id, amount
    form = await request.form()
    payload = dict(form)
    log.warning("CACTUS_HOOK form=%s", payload)

    order_id = str(payload.get("order_id") or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="order_id missing")

    # По доке: после webhook обязательно проверить статус через API /get => ACCEPT/WAIT
    provider = get_provider("cactus")
    status = await provider.check_status(order_id)  # должен вернуть "paid" если ACCEPT

    if status != "paid":
        return {"ok": True, "status": status}

    order = await _find_created_order_by_id(order_id)
    if not order:
        return {"ok": True, "status": "already_processed_or_not_found"}

    await fulfill_paid_order(bot, settings, order)
    return {"ok": True, "status": "paid_processed"}


# -------------------- CRYPTOBOT --------------------
@app.post("/hooks/crypto")
async def crypto_hook(request: Request):
    _check_secret(request)

    raw = await request.body()

    data: dict[str, Any] = {}
    # Обычно JSON, но на всякий поддержим и form
    try:
        data = await request.json()
    except Exception:
        try:
            form = await request.form()
            data = dict(form)
        except Exception:
            data = {}

    log.warning(
        "CRYPTO_HOOK raw=%s json=%s",
        raw.decode("utf-8", "ignore"),
        json.dumps(data, ensure_ascii=False),
    )

    # 1) invoice_id
    invoice_id = str(
        data.get("invoice_id")
        or data.get("invoiceId")
        or data.get("id")
        or ""
    ).strip()

    # 2) иногда полезно payload (если ты его кладешь при создании инвойса)
    payload = str(data.get("payload") or data.get("data") or "").strip()
    order_id_from_payload = ""
    if payload.startswith("order:"):
        order_id_from_payload = payload.split("order:", 1)[1].strip()

    provider = get_provider("crypto")

    # Если в payload есть order_id — ищем по order.id и проверяем статус по сохраненному invoice_id
    if order_id_from_payload:
        order = await _find_created_order_by_id(order_id_from_payload)
        if not order:
            return {"ok": True, "status": "already_processed_or_not_found"}

        if not order.provider_invoice_id:
            return {"ok": True, "status": "order_missing_invoice_id"}

        st = await provider.check_status(order.provider_invoice_id)
        if st != "paid":
            return {"ok": True, "status": st}

        await fulfill_paid_order(bot, settings, order)
        return {"ok": True, "status": "paid_processed"}

    # Иначе — работаем по invoice_id
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