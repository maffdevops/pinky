from __future__ import annotations

from .base import PaymentProvider
from .cryptobot import CryptoBotProvider
from .cactuspay import CactusPayProvider


_providers: dict[str, PaymentProvider] = {
    "crypto": CryptoBotProvider(),
    "cactus": CactusPayProvider(),
}


def get_provider(name: str) -> PaymentProvider:
    if name not in _providers:
        raise ValueError(f"Unknown provider: {name}")
    return _providers[name]
