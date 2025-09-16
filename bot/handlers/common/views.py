from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from backend.src.common.enums import UserRole
from bot.clients.disputes_client import DisputesClient
from bot.clients.system_client import SystemClient
from bot.dto import UserDTO
from bot.filters.filters import RoleFilter
from bot.messages import CommonMessages, DisputeMessages

from . import service

common_router = Router(name="common_handlers")


@common_router.message(Command("test_api"))
async def test_api_connection(message: Message, user: UserDTO, system_client: SystemClient):
    """Тестирование соединения с API (требует авторизации)."""
    await message.answer(CommonMessages.API_TESTING)
    response_text = await service.get_api_status_text(system_client)
    await message.answer(response_text)


@common_router.message(Command("orders"))
async def orders_handler(message: Message, user: UserDTO):
    """Показать заказы в зависимости от роли (требует авторизации)."""
    text = service.get_orders_text_by_role(user.role)
    await message.answer(text)


@common_router.message(Command("dispute"), RoleFilter(UserRole.SHOP, UserRole.COURIER))
async def dispute_handler(message: Message, user: UserDTO):
    """Открыть новый спор (для магазинов и курьеров)."""
    text = service.get_new_dispute_text()
    await message.answer(text)


@common_router.message(
    Command("disputes"), RoleFilter(UserRole.SHOP, UserRole.COURIER, UserRole.ADMIN)
)
async def disputes_handler(message: Message, user: UserDTO, disputes_client: DisputesClient):
    """Показать споры пользователя."""
    await message.answer(DisputeMessages.LOADING_DISPUTES)
    response_text = await service.get_user_disputes_text(user.telegram_id, disputes_client)
    await message.answer(response_text)
