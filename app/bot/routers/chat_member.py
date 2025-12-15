from aiogram import Router
from aiogram.types import ChatMemberUpdated

from ..services.subscriptions import handle_member_update


router = Router()


@router.chat_member()
async def on_member_update(event: ChatMemberUpdated) -> None:
    await handle_member_update(event)