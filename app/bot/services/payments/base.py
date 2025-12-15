from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    pay_url: str

    # Доп. данные (особенно полезно для CactusPay)
    pay_until: str | None = None          # например: "Wed, 12 Feb 2025 22:50:52 +0300"
    pay_until_timestamp: int | None = None
    receiver_qr: str | None = None        # ссылка на qr.nspk.ru


class PaymentProvider(Protocol):
    name: str

    async def create_invoice(self, order_id: str, amount_rub: int) -> Invoice:
        ...

    async def check_status(self, invoice_id: str) -> str:
        """Return: created/paid/expired/canceled"""
        ...

    async def cancel(self, invoice_id: str) -> None:
        ...