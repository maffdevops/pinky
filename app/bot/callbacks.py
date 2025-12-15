from aiogram.filters.callback_data import CallbackData


class MenuCb(CallbackData, prefix="menu"):
    action: str


class TariffCb(CallbackData, prefix="tariff"):
    code: str


class ConfirmCb(CallbackData, prefix="confirm"):
    action: str  # yes/no/back


class PayMethodCb(CallbackData, prefix="paym"):
    provider: str  # cactus/crypto
    tariff: str


class OrderCb(CallbackData, prefix="order"):
    action: str  # pay/cancel
    order_id: str
