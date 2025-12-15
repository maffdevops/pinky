from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class Tariff:
    code: str
    title: str
    price_rub: int
    duration: timedelta | None  # None => forever


TARIFFS: dict[str, Tariff] = {
    "forever": Tariff(code="forever", title="🏆 НАВСЕГДА", price_rub=990, duration=None),
    "month": Tariff(code="month", title="🗓️ МЕСЯЦ", price_rub=450, duration=timedelta(days=30)),
    "week": Tariff(code="week", title="📆 НЕДЕЛЯ", price_rub=250, duration=timedelta(days=7)),
    "trial": Tariff(code="trial", title="🧪 ПРОБНИК", price_rub=200, duration=timedelta(hours=24)),
}