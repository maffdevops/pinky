from __future__ import annotations

import os
from typing import Optional

from aiogram.types import Message, FSInputFile

from ..config import Settings
from ..db import repo


async def replace_screen(
    message: Message,
    text: str,
    photo_path: Optional[str] = None,
    reply_markup=None,
) -> Message:
    """
    Отправляет новый "экран" и удаляет предыдущий (по last_screen_message_id из БД).
    photo_path можно передавать как "assets/images/xxx.jpg" — путь будет сделан абсолютным.
    """
    settings = Settings()

    user_id = message.from_user.id if message.from_user else message.chat.id

    # 1) удалить прошлый экран
    try:
        last_chat_id, last_msg_id = await repo.get_last_screen(settings.db_path_abs, user_id)
        if last_chat_id and last_msg_id:
            await message.bot.delete_message(chat_id=last_chat_id, message_id=last_msg_id)
    except Exception:
        pass

    # 2) удалить текущее сообщение (если это callback по старому экрану)
    try:
        await message.delete()
    except Exception:
        pass

    # 3) отправить новый экран
    abs_photo_path = None
    if photo_path:
        abs_photo_path = settings.assets_path(photo_path)

    if abs_photo_path and os.path.exists(abs_photo_path):
        sent = await message.answer_photo(
            photo=FSInputFile(abs_photo_path),
            caption=text,
            reply_markup=reply_markup,
        )
    else:
        sent = await message.answer(text, reply_markup=reply_markup)

    # 4) сохранить новый экран как последний
    try:
        await repo.set_last_screen(settings.db_path_abs, user_id, sent.chat.id, sent.message_id)
    except Exception:
        pass

    return sent