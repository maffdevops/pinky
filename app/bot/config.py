from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Корень проекта (app/bot/config.py -> project root)
    BASE_DIR: Path = Path(__file__).resolve().parents[2]

    # Telegram
    BOT_TOKEN: str = Field(...)
    ADMIN_IDS: str = Field(default="")  # comma-separated
    MANAGER_URL: str = Field(default="https://t.me/")
    TARGET_CHAT_ID: int = Field(...)

    # Payments
    CRYPTOBOT_TOKEN: str = Field(default="")
    CACTUSPAY_API_KEY: str = Field(default="")
    CACTUSPAY_SHOP_ID: str = Field(default="")

    # App
    DB_PATH: str = Field(default="bot.db")  # можно относительный, будет резолвиться от BASE_DIR
    ORDER_TTL_MINUTES: int = Field(default=10)
    TIMEZONE: str = Field(default="Europe/Moscow")

    @property
    def admin_ids(self) -> list[int]:
        raw = self.ADMIN_IDS.strip()
        if not raw:
            return []
        return [int(x.strip()) for x in raw.split(",") if x.strip()]

    def assets_path(self, relative: str) -> str:
        return str((self.BASE_DIR / relative).resolve())

    @property
    def db_path_abs(self) -> str:
        p = Path(self.DB_PATH)
        if not p.is_absolute():
            p = self.BASE_DIR / p
        return str(p.resolve())