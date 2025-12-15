from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .connection import connect


# -------------------------
# Orders
# -------------------------

@dataclass
class Order:
    id: str
    user_id: int
    tariff_code: str
    price_rub: int
    provider: str
    status: str
    created_at: str
    expires_at: str
    provider_invoice_id: Optional[str] = None
    pay_url: Optional[str] = None
    paid_at: Optional[str] = None


def _row_to_order(row) -> Order:
    return Order(
        id=row[0],
        user_id=row[1],
        tariff_code=row[2],
        price_rub=row[3],
        provider=row[4],
        status=row[5],
        provider_invoice_id=row[6],
        pay_url=row[7],
        created_at=row[8],
        expires_at=row[9],
        paid_at=row[10],
    )


async def ensure_user(db_path: str, user_id: int) -> None:
    conn = await connect(db_path)
    try:
        await conn.execute(
            "INSERT OR IGNORE INTO users(user_id, created_at) VALUES(?, ?)",
            (user_id, datetime.utcnow().isoformat()),
        )
        await conn.commit()
    finally:
        await conn.close()


async def create_order(
    db_path: str,
    user_id: int,
    tariff_code: str,
    price_rub: int,
    provider: str,
    ttl_minutes: int,
) -> Order:
    await ensure_user(db_path, user_id)

    order_id = uuid.uuid4().hex[:10]
    now = datetime.utcnow()
    expires = now + timedelta(minutes=ttl_minutes)

    order = Order(
        id=order_id,
        user_id=user_id,
        tariff_code=tariff_code,
        price_rub=price_rub,
        provider=provider,
        status="created",
        created_at=now.isoformat(),
        expires_at=expires.isoformat(),
    )

    conn = await connect(db_path)
    try:
        await conn.execute(
            """
            INSERT INTO orders(
              id, user_id, tariff_code, price_rub, provider, status, created_at, expires_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.id,
                order.user_id,
                order.tariff_code,
                order.price_rub,
                order.provider,
                order.status,
                order.created_at,
                order.expires_at,
            ),
        )
        await conn.commit()
    finally:
        await conn.close()

    return order


async def update_order_payment(
    db_path: str,
    order_id: str,
    provider_invoice_id: str,
    pay_url: str,
) -> None:
    conn = await connect(db_path)
    try:
        await conn.execute(
            """
            UPDATE orders
            SET provider_invoice_id=?, pay_url=?
            WHERE id=?
            """,
            (provider_invoice_id, pay_url, order_id),
        )
        await conn.commit()
    finally:
        await conn.close()


async def set_order_status(db_path: str, order_id: str, status: str) -> None:
    conn = await connect(db_path)
    try:
        await conn.execute(
            "UPDATE orders SET status=? WHERE id=?",
            (status, order_id),
        )
        await conn.commit()
    finally:
        await conn.close()


async def get_order_by_id(db_path: str, order_id: str) -> Optional[Order]:
    conn = await connect(db_path)
    try:
        cur = await conn.execute(
            """
            SELECT id, user_id, tariff_code, price_rub, provider, status,
                   provider_invoice_id, pay_url, created_at, expires_at, paid_at
            FROM orders
            WHERE id=?
            """,
            (order_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return _row_to_order(row)
    finally:
        await conn.close()


async def get_created_orders(db_path: str, limit: int = 50) -> list[Order]:
    conn = await connect(db_path)
    try:
        cur = await conn.execute(
            """
            SELECT id, user_id, tariff_code, price_rub, provider, status,
                   provider_invoice_id, pay_url, created_at, expires_at, paid_at
            FROM orders
            WHERE status='created'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cur.fetchall()
        return [_row_to_order(r) for r in rows]
    finally:
        await conn.close()


async def get_expired_created_orders(db_path: str, now_iso: str) -> list[Order]:
    conn = await connect(db_path)
    try:
        cur = await conn.execute(
            """
            SELECT id, user_id, tariff_code, price_rub, provider, status,
                   provider_invoice_id, pay_url, created_at, expires_at, paid_at
            FROM orders
            WHERE status='created' AND expires_at <= ?
            ORDER BY expires_at ASC
            """,
            (now_iso,),
        )
        rows = await cur.fetchall()
        return [_row_to_order(r) for r in rows]
    finally:
        await conn.close()


async def mark_order_paid(db_path: str, order_id: str) -> None:
    conn = await connect(db_path)
    try:
        await conn.execute(
            """
            UPDATE orders
            SET status='paid', paid_at=?
            WHERE id=? AND status='created'
            """,
            (datetime.utcnow().isoformat(), order_id),
        )
        await conn.commit()
    finally:
        await conn.close()


# -------------------------
# Subscriptions
# -------------------------

@dataclass
class Subscription:
    id: str
    user_id: int
    tariff_code: str
    starts_at: str
    ends_at: Optional[str]  # NULL => forever
    status: str             # active/expired/revoked
    order_id: str


def _row_to_subscription(row) -> Subscription:
    return Subscription(
        id=row[0],
        user_id=row[1],
        tariff_code=row[2],
        starts_at=row[3],
        ends_at=row[4],
        status=row[5],
        order_id=row[6],
    )


async def create_subscription(
    db_path: str,
    user_id: int,
    tariff_code: str,
    *,
    starts_at_iso: str,
    ends_at_iso: Optional[str],
    order_id: str,
    status: str = "active",
) -> Subscription:
    """
    Создаёт подписку. ends_at_iso=None означает "навсегда".
    """
    sub_id = uuid.uuid4().hex[:12]

    conn = await connect(db_path)
    try:
        await conn.execute(
            """
            INSERT INTO subscriptions(id, user_id, tariff_code, starts_at, ends_at, status, order_id)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (sub_id, user_id, tariff_code, starts_at_iso, ends_at_iso, status, order_id),
        )
        await conn.commit()
    finally:
        await conn.close()

    return Subscription(
        id=sub_id,
        user_id=user_id,
        tariff_code=tariff_code,
        starts_at=starts_at_iso,
        ends_at=ends_at_iso,
        status=status,
        order_id=order_id,
    )


async def get_active_subscription_for_user(db_path: str, user_id: int) -> Optional[Subscription]:
    """
    Берём активную подписку пользователя (самую свежую).
    """
    conn = await connect(db_path)
    try:
        cur = await conn.execute(
            """
            SELECT id, user_id, tariff_code, starts_at, ends_at, status, order_id
            FROM subscriptions
            WHERE user_id=? AND status='active'
            ORDER BY starts_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return _row_to_subscription(row)
    finally:
        await conn.close()


async def get_due_subscriptions_to_expire(db_path: str, now_iso: str, limit: int = 200) -> list[Subscription]:
    """
    Активные подписки, у которых ends_at наступил (и ends_at не NULL).
    """
    conn = await connect(db_path)
    try:
        cur = await conn.execute(
            """
            SELECT id, user_id, tariff_code, starts_at, ends_at, status, order_id
            FROM subscriptions
            WHERE status='active' AND ends_at IS NOT NULL AND ends_at <= ?
            ORDER BY ends_at ASC
            LIMIT ?
            """,
            (now_iso, limit),
        )
        rows = await cur.fetchall()
        return [_row_to_subscription(r) for r in rows]
    finally:
        await conn.close()


async def set_subscription_status(db_path: str, sub_id: str, status: str) -> None:
    conn = await connect(db_path)
    try:
        await conn.execute(
            "UPDATE subscriptions SET status=? WHERE id=?",
            (status, sub_id),
        )
        await conn.commit()
    finally:
        await conn.close()


async def revoke_active_subscriptions_for_user(db_path: str, user_id: int) -> None:
    """
    Если пользователь вышел из группы/канала — считаем доступ отозванным.
    (А дальше: "вышел = повторная оплата")
    """
    conn = await connect(db_path)
    try:
        await conn.execute(
            """
            UPDATE subscriptions
            SET status='revoked'
            WHERE user_id=? AND status='active'
            """,
            (user_id,),
        )
        await conn.commit()
    finally:
        await conn.close()

async def get_last_screen(db_path: str, user_id: int) -> tuple[int | None, int | None]:
    conn = await connect(db_path)
    try:
        cur = await conn.execute(
            "SELECT last_screen_chat_id, last_screen_message_id FROM users WHERE user_id=?",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None, None
        return row[0], row[1]
    finally:
        await conn.close()


async def set_last_screen(db_path: str, user_id: int, chat_id: int, message_id: int) -> None:
    await ensure_user(db_path, user_id)

    conn = await connect(db_path)
    try:
        await conn.execute(
            """
            UPDATE users
            SET last_screen_chat_id=?, last_screen_message_id=?
            WHERE user_id=?
            """,
            (chat_id, message_id, user_id),
        )
        await conn.commit()
    finally:
        await conn.close()