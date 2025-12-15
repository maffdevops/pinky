from __future__ import annotations

import logging
from typing import Any

import aiohttp

from ...config import Settings
from .base import Invoice

log = logging.getLogger(__name__)


class CryptoBotProvider:
    """
    Crypto Pay API (CryptoBot):
      - POST https://pay.crypt.bot/api/createInvoice
      - POST https://pay.crypt.bot/api/getInvoices
      - POST https://pay.crypt.bot/api/deleteInvoice

    Авторизация: заголовок Crypto-Pay-API-Token
    """

    name = "crypto"

    def __init__(self) -> None:
        self._settings = Settings()
        self._token = self._settings.CRYPTOBOT_TOKEN.strip()

        if not self._token:
            log.warning("CRYPTOBOT_TOKEN is empty — CryptoBotProvider will not work")

        self._base = "https://pay.crypt.bot/api/"
        self._timeout = aiohttp.ClientTimeout(total=15)

        # можно ограничить активы, которые примешь
        self._accepted_assets = "USDT,TON,BTC,ETH,LTC,BNB,TRX,USDC"

        # 10 минут (совпадает с ORDER_TTL_MINUTES=10)
        self._expires_in_seconds = 600

    async def create_invoice(self, order_id: str, amount_rub: int) -> Invoice:
        """
        Создаём инвойс в RUB (currency_type=fiat, fiat=RUB).
        Возвращаем invoice_id и ссылку на оплату (лучше mini_app_invoice_url).
        """
        payload = {
            "currency_type": "fiat",
            "fiat": "RUB",
            "amount": str(float(amount_rub)),
            "accepted_assets": self._accepted_assets,
            "description": "Telegram access",
            "payload": f"order:{order_id}",
            "expires_in": self._expires_in_seconds,
        }

        data = await self._post("createInvoice", payload)

        result = data.get("result") or {}
        invoice_id = result.get("invoice_id")
        if invoice_id is None:
            raise RuntimeError(f"CryptoBot createInvoice missing invoice_id: {data}")

        pay_url = (
            result.get("mini_app_invoice_url")
            or result.get("bot_invoice_url")
            or result.get("web_app_invoice_url")
        )
        if not pay_url:
            raise RuntimeError(f"CryptoBot createInvoice missing pay url: {data}")

        return Invoice(invoice_id=str(invoice_id), pay_url=str(pay_url))

    async def check_status(self, invoice_id: str) -> str:
        """
        status: active / paid / expired
        """
        data = await self._post("getInvoices", {"invoice_ids": invoice_id})
        invoices = (data.get("result") or {}).get("items") or []

        if not invoices:
            return "created"

        inv = invoices[0]
        status = (inv.get("status") or "").lower()

        if status == "paid":
            return "paid"
        if status == "expired":
            return "expired"
        return "created"  # active/прочее

    async def cancel(self, invoice_id: str) -> None:
        """
        deleteInvoice — удаляет инвойс.
        """
        try:
            await self._post("deleteInvoice", {"invoice_id": int(invoice_id)})
        except Exception:
            log.exception("CryptoBot deleteInvoice failed (ignored), invoice_id=%s", invoice_id)

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._token:
            raise RuntimeError("CRYPTOBOT_TOKEN is not set")

        url = f"{self._base}{method}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Crypto-Pay-API-Token": self._token,
        }

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(url, json=payload, headers=headers) as r:
                text = await r.text()
                if r.status >= 400:
                    raise RuntimeError(f"CryptoBot HTTP {r.status}: {text}")

                try:
                    data = await r.json()
                except Exception as e:
                    raise RuntimeError(f"CryptoBot invalid JSON: {text}") from e

        if not data.get("ok", False):
            raise RuntimeError(f"CryptoBot API error: {data.get('error') or data}")

        return data