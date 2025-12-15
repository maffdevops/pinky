from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Bot

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class InviteResult:
    url: str
    expires_at: datetime


async def create_one_time_invite(
    bot: Bot,
    chat_id: int,
    *,
    ttl_minutes: int = 60,
    name: str = "🧾 Доступ (одноразовая ссылка)",
) -> InviteResult:
    """
    Создаёт одноразовую инвайт-ссылку (member_limit=1).
    ttl_minutes — сколько ссылка будет жить (на случай если человек не зашёл сразу).
    """
    expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)

    invite = await bot.create_chat_invite_link(
        chat_id=chat_id,
        name=name,
        member_limit=1,
        expire_date=expires_at,
        creates_join_request=False,
    )

    if not invite.invite_link:
        raise RuntimeError("Telegram did not return invite_link")

    return InviteResult(url=invite.invite_link, expires_at=expires_at)


async def kick_user(bot: Bot, chat_id: int, user_id: int) -> None:
    """
    Кикаем пользователя из чата/канала.
    Делается бан+разбан, чтобы:
      - пользователь сразу вылетел
      - и мог снова зайти ТОЛЬКО по новой оплате/новой ссылке
    """
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
    except Exception:
        log.exception("Failed to ban user %s in chat %s", user_id, chat_id)

    # unban чтобы не оставлять вечный бан
    try:
        await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
    except Exception:
        log.exception("Failed to unban user %s in chat %s", user_id, chat_id)