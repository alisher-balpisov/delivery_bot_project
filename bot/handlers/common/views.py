from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from backend.src.common.enums import UserRole
from bot.filters import RoleFilter
from bot.messages import CommonMessages, DisputeMessages

from . import service

common_router = Router(name="common_handlers")


@common_router.message(Command("test_api"))
async def test_api_connection(message: Message, user_data: dict):
    """Тестирование соединения с API (требует авторизации)."""
    await message.answer(CommonMessages.API_TESTING)
    text = await service.get_api_status_text()
    await message.answer(text)


@common_router.message(Command("orders"))
async def orders_handler(message: Message, user_data: dict):
    """Показать заказы в зависимости от роли (требует авторизации)."""
    role = user_data.get("role", UserRole.GUEST)
    text = service.get_orders_text_by_role(role)
    await message.answer(text)


@common_router.message(Command("dispute"), RoleFilter([UserRole.SHOP, UserRole.COURIER]))
async def dispute_handler(message: Message, user_data: dict):
    """Открыть новый спор (для магазинов и курьеров)."""
    text = service.get_new_dispute_text()
    await message.answer(text)


@common_router.message(
    Command("disputes"), RoleFilter([UserRole.SHOP, UserRole.COURIER, UserRole.ADMIN])
)
async def disputes_handler(message: Message, user_data: dict):
    """Показать споры пользователя."""
    await message.answer(DisputeMessages.LOADING_DISPUTES)
    telegram_id = message.from_user.id
    text = await service.get_user_disputes_text(telegram_id)
    await message.answer(text)
