from __future__ import annotations

import logging
from pathlib import Path

from .connection import connect
from ..config import Settings

log = logging.getLogger(__name__)


async def init_db(settings: Settings) -> None:
    # гарантируем, что папка под БД существует
    Path(settings.db_path_abs).parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(__file__).with_name("schema.sql")
    schema = schema_path.read_text(encoding="utf-8")

    log.info("DB init: %s", settings.db_path_abs)

    conn = await connect(settings.db_path_abs)
    try:
        await conn.executescript(schema)
        await conn.commit()
    finally:
        await conn.close()