from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from ..config import Settings
from ..callbacks import MenuCb
from ..keyboards.main_menu import main_menu_kb
from ..utils.message_cleanup import replace_screen


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, settings: Settings) -> None:
    text = (
        "🍩 *Добро пожаловать!*\n\n"
        "👇 Выберите, что вам нужно:"
    )

    await replace_screen(
        message=message,
        text=text,
        photo_path="assets/images/main_menu.jpg",
        reply_markup=main_menu_kb(settings.MANAGER_URL),
    )


@router.callback_query(MenuCb.filter(F.action == "home"))
async def back_home(call: CallbackQuery, settings: Settings) -> None:
    await call.answer()

    text = (
        "🏠 *Главное меню*\n\n"
        "👇 Выберите действие:"
    )

    await replace_screen(
        message=call.message,
        text=text,
        photo_path="assets/images/main_menu.jpg",
        reply_markup=main_menu_kb(settings.MANAGER_URL),
    )