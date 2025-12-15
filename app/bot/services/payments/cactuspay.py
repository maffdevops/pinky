from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp

from ...config import Settings
from .base import Invoice

log = logging.getLogger(__name__)


class CactusPayProvider:
    """
    CactusPay API:
      - create: POST https://lk.cactuspay.pro/api/?method=create
      - get:    POST https://lk.cactuspay.pro/api/?method=get   (ACCEPT / WAIT)
      - cancel: POST https://lk.cactuspay.pro/api/?method=CANCEL_DETAILS  (для h2h)

    ВАЖНО:
      - Для "РФ | СБП | QR" обычно используем method="nspk".
      - h2h требует user_ip, а в Telegram его обычно нет, поэтому по умолчанию h2h=False.
    """

    name = "cactus"

    def __init__(self) -> None:
        self._settings = Settings()
        self._token = self._settings.CACTUSPAY_API_KEY.strip()
        self._timeout = aiohttp.ClientTimeout(total=20)
        self._base = "https://lk.cactuspay.pro/api/?method="

        if not self._token:
            log.warning("CACTUSPAY_API_KEY is empty — CactusPayProvider will not work")

        self._default_method = "nspk"  # card, sbp, yoomoney, crypto, nspk

        # h2h: выключено, так как нужен user_ip
        self._use_h2h = False
        self._h2h_user_ip: Optional[str] = None

    async def create_invoice(self, order_id: str, amount_rub: int) -> Invoice:
        if not self._token:
            raise RuntimeError("CACTUSPAY_API_KEY is not set")

        payload: dict[str, Any] = {
            "token": self._token,
            "order_id": order_id,
            "amount": float(amount_rub),
            "description": "Telegram access",
            "method": self._default_method,
        }

        if self._use_h2h:
            payload["h2h"] = True
            if not self._h2h_user_ip:
                raise RuntimeError("CactusPay h2h enabled but user_ip is not set")
            payload["user_ip"] = self._h2h_user_ip

        data = await self._post_json("create", payload)
        if data.get("status") != "success":
            raise RuntimeError(f"CactusPay create failed: {data}")

        resp = data.get("response") or {}

        pay_url = resp.get("url")
        if not pay_url:
            raise RuntimeError(f"CactusPay create missing response.url: {data}")

        # optional (может быть, если API вернул requisite)
        req_resp = (resp.get("requisite") or {}).get("response") or {}

        pay_until = req_resp.get("until")  # строка вроде "Wed, 12 Feb 2025 22:50:52 +0300"
        pay_until_ts = req_resp.get("until_timestamp")  # unix timestamp
        receiver_qr = req_resp.get("receiverQR")  # ссылка на qr.nspk.ru

        return Invoice(
            invoice_id=order_id,               # order_id == invoice_id для CactusPay
            pay_url=str(pay_url),
            pay_until=str(pay_until) if pay_until else None,
            pay_until_timestamp=int(pay_until_ts) if pay_until_ts else None,
            receiver_qr=str(receiver_qr) if receiver_qr else None,
        )

    async def check_status(self, invoice_id: str) -> str:
        if not self._token:
            raise RuntimeError("CACTUSPAY_API_KEY is not set")

        payload = {"token": self._token, "order_id": invoice_id}
        data = await self._post_json("get", payload)

        if data.get("status") != "success":
            # не ломаем заказ — просто ждём дальше
            log.warning("CactusPay get not success: %s", data)
            return "created"

        resp = data.get("response") or {}
        st = str(resp.get("status") or "").upper()  # ACCEPT / WAIT

        if st == "ACCEPT":
            return "paid"

        return "created"

    async def cancel(self, invoice_id: str) -> None:
        """
        CANCEL_DETAILS — актуально для h2h реквизитов.
        Для обычной "url оплаты" может быть неприменимо — ошибки игнорируем.
        """
        if not self._token:
            return

        payload = {"token": self._token, "order_id": invoice_id}
        try:
            data = await self._post_json("CANCEL_DETAILS", payload)
            if data.get("status") != "success":
                log.warning("CactusPay cancel not success: %s", data)
        except Exception:
            log.exception("CactusPay cancel error (ignored)")

    async def _post_json(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}{method}"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(url, json=payload, headers=headers) as r:
                text = await r.text()
                if r.status >= 400:
                    raise RuntimeError(f"CactusPay HTTP {r.status}: {text}")

                try:
                    return await r.json()
                except Exception as e:
                    raise RuntimeError(f"CactusPay invalid JSON: {text}") from e