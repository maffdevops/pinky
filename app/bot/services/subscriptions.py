from __future__ import annotations

import logging

from aiogram.types import ChatMemberUpdated

from ..config import Settings
from ..db import repo

log = logging.getLogger(__name__)


async def handle_member_update(event: ChatMemberUpdated) -> None:
    """
    Отслеживаем выход/кик из TARGET_CHAT_ID.
    Если пользователь перестал быть участником — помечаем активные подписки как revoked.
    """
    settings = Settings()

    # работаем только по целевому чату
    if event.chat.id != settings.TARGET_CHAT_ID:
        return

    # user, которого коснулось событие (а не админ/бот, который кикнул)
    user_id = getattr(event.new_chat_member.user, "id", None)
    if user_id is None:
        return

    # новое состояние в чате: member/administrator/left/kicked/restricted...
    new_status = event.new_chat_member.status

    if new_status in ("left", "kicked"):
        try:
            await repo.revoke_active_subscriptions_for_user(settings.db_path_abs, user_id)
            log.info("Revoked subscriptions for user %s (status=%s)", user_id, new_status)
        except Exception:
            log.exception("Failed to revoke subscriptions for user %s", user_id)