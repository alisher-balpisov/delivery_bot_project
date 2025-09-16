from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from backend.src.common.enums import UserRole
from bot.messages import CommonMessages, PublicMessages

from . import service

public_router = Router(name="public_handlers")


@public_router.message(Command("help"))
async def help_handler(message: Message, user_data: dict):
    """Показать доступные команды."""
    role = user_data.get("role", UserRole.GUEST)

    # Вызываем сервисную функцию для генерации текста
    help_text = service.generate_help_text(role)

    await message.answer(help_text)


@public_router.message(F.text)
async def handle_plain_text(message: Message, user_data: dict):
    """Обработчик обычных текстовых сообщений."""
    text_lower = (message.text or "").lower()

    if text_lower in PublicMessages.MENU_KEYWORDS:
        await message.answer(CommonMessages.USE_HELP)
    elif text_lower in PublicMessages.STATUS_KEYWORDS:
        # Вызываем сервисную функцию для получения текста статуса
        status_text = service.get_user_status_text(user_data)
        await message.answer(status_text)
    else:
        await message.answer(CommonMessages.UNKNOWN_COMMAND)
