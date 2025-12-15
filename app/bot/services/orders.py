from __future__ import annotations

from ..config import Settings
from ..db.repo import Order as OrderModel
from ..db import repo


async def create_order(user_id: int, tariff_code: str, price_rub: int, provider: str) -> OrderModel:
    settings = Settings()
    return await repo.create_order(
        db_path=settings.db_path_abs,
        user_id=user_id,
        tariff_code=tariff_code,
        price_rub=price_rub,
        provider=provider,
        ttl_minutes=settings.ORDER_TTL_MINUTES,
    )


async def attach_invoice(order_id: str, provider_invoice_id: str, pay_url: str) -> None:
    settings = Settings()
    await repo.update_order_payment(
        db_path=settings.db_path_abs,
        order_id=order_id,
        provider_invoice_id=provider_invoice_id,
        pay_url=pay_url,
    )


async def cancel_order(order_id: str) -> None:
    settings = Settings()
    await repo.set_order_status(settings.db_path_abs, order_id, "canceled")